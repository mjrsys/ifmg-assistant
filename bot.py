import os
import asyncio
import requests
import logging
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes)
from suap import (consultar_boletim, formatar_boletim, obter_periodo_mais_recente, listar_periodos, verificar_conexao_suap)
from database.db import (criar_estado_oauth, remover_usuario, obter_tokens)
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)


logger = logging.getLogger("ifmg-assistant")
logging.getLogger("httpx").setLevel(logging.WARNING)

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
OAUTH_BASE_URL = os.getenv("OAUTH_BASE_URL")
BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "ifmg_assistant.db"
BACKUP_DIR = BASE_DIR / "backups"

def verificar_oauth():
    try:
        resposta = requests.get(
            "http://127.0.0.1:8000",
            timeout=3
        )
        return True
    except requests.exceptions.RequestException:
        return False


def verificar_banco():
    try:
        with sqlite3.connect(
            f"file:{DATABASE_PATH}?mode=rw",
            uri=True,
            timeout=3
        ) as conexao:
            resultado = conexao.execute(
                "PRAGMA quick_check"
            ).fetchone()

        return resultado is not None and resultado[0] == "ok"

    except sqlite3.Error:
        return False


def verificar_backup():
    try:
        backups = list(
            BACKUP_DIR.glob("ifmg-assistant_*.db")
        )

        if not backups:
            return None

        ultimo = max(
            backups,
            key=lambda arquivo: arquivo.stat().st_mtime
        )

        idade = datetime.now().timestamp() - ultimo.stat().st_mtime

        return idade <= 26 * 60 * 60

    except OSError:
        return False


def verificar_armazenamento():
    try:
        uso = shutil.disk_usage(BASE_DIR)
        percentual = (uso.used / uso.total) * 100
        return percentual

    except OSError:
        return None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! 😎 \n\n"
        "Sou o IFMG Assistant.\n"
        "Um assistente capaz de realizar consultas no SUAP para te ajudar :)\n\n"
        "Comandos disponíveis:\n"
        "/conectar - Vincular sua conta SUAP\n"
        "/notas - Consultar suas notas\n"
        "/desconectar - Desvincular sua conta\n"
        "/status - Verificar funcionamento\n"
        "/periodos - Listar períodos letivos disponíveis\n"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Por segurança, utilize /status em uma conversa privada."
        )
        return

    telegram_id = update.effective_user.id

    await update.message.reply_text(
        "🔎 Verificando sua conexão com o SUAP..."
    )

    try:
        conectado = await asyncio.to_thread(
            verificar_conexao_suap,
            telegram_id
        )

        if conectado:
            status_suap = "🟢 Conexão autenticada"
            orientacao = (
                "Você pode consultar suas notas com /notas."
            )
        else:
            status_suap = "🔴 Autorização recusada"
            orientacao = (
                "Execute /conectar para vincular novamente sua conta."
            )

    except ValueError:
        status_suap = "🔴 Conta não conectada"
        orientacao = (
            "Execute /conectar para vincular sua conta SUAP."
        )

    except RuntimeError as erro:
        logger.error("Erro de autenticação no status: %s", type(erro).__name__)

        status_suap = "🟠 Falha na autenticação"
        orientacao = (
            "Não foi possível validar sua conta. "
            "Tente /conectar novamente."
        )

    except requests.exceptions.Timeout:
        status_suap = "🟠 SUAP sem resposta"
        orientacao = (
            "Não foi possível verificar agora. Tente novamente."
        )

    except requests.exceptions.RequestException:
        status_suap = "🟠 SUAP indisponível"
        orientacao = (
            "Não foi possível consultar o SUAP neste momento."
        )

    except Exception as erro:
        logger.exception("Erro inesperado no status")

        status_suap = "🟠 Erro na verificação"
        orientacao = "Tente novamente mais tarde."

    oauth_ok = await asyncio.to_thread(verificar_oauth)
    banco_ok = await asyncio.to_thread(verificar_banco)
    backup_ok = await asyncio.to_thread(verificar_backup)
    disco = await asyncio.to_thread(verificar_armazenamento)

    status_oauth = "🟢 OAuth: Funcionando" if oauth_ok else "🔴 OAuth: Indisponível"
    status_banco = "🟢 Banco de dados: Acessível" if banco_ok else "🔴 Banco de dados: Com problemas"

    if backup_ok is True:
        status_backup = "🟢 Atualizado"
    elif backup_ok is False:
        status_backup = "🟠 Desatualizado"
    else:
        status_backup = "🔴 Nenhum backup encontrado"

    status_disco = (
        f"{disco:.1f}% utilizado"
        if disco is not None
        else "Não disponível"
    )

    mensagem = (
        "📊 *IFMG Assistant — Monitoramento*\n\n"
        "⚙️ *Serviços*\n"
        "🟢 Telegram Bot Service: Operacional\n"
        f"{status_oauth}\n"
        f"{status_banco}\n"
        f"Backup {status_backup}\n\n"
        "🖥️ *Infraestrutura*\n"
        "Sistema: Debian 13\n"
        f"Armazenamento: {status_disco}\n\n"
        f"📚 SUAP: {status_suap}\n\n"
        f"{orientacao}\n\n"
        f"🕒 Verificado: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    )

    await update.message.reply_text(
        mensagem,
        parse_mode="Markdown"
    )

async def conectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Por segurança, utilize /conectar em uma conversa privada com o bot."
        )
        return

    if not OAUTH_BASE_URL:
        await update.message.reply_text(
            "❌ O endereço do servidor OAuth não está configurado."
        )
        return

    try:
        telegram_id = update.effective_user.id

        state = await asyncio.to_thread(
            criar_estado_oauth,
            telegram_id
        )

        link = (
            f"{OAUTH_BASE_URL.rstrip('/')}/login?state={state}"
        )

        await update.message.reply_text(
            "🔐 Vamos conectar sua conta do SUAP!\n\n"
            "1. Acesse o link abaixo.\n"
            "2. Entre com sua conta institucional.\n"
            "3. Autorize o acesso solicitado.\n\n"
            f"🔗 {link}\n\n"
            "O link expira em 10 minutos e só pode ser utilizado uma vez."
        )

    except Exception:
        logger.exception("Erro ao iniciar conexão OAuth")

        await update.message.reply_text(
            "❌ Não foi possível iniciar a conexão com o SUAP. Tente novamente."
        )


async def desconectar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Utilize este comando em uma conversa privada com o bot."
        )
        return

    try:
        telegram_id = update.effective_user.id

        await asyncio.to_thread(
            remover_usuario,
            telegram_id
        )

        await update.message.reply_text(
            "🔒 Sua conta foi desvinculada do IFMG Assistant.\n\n"
            "Os tokens armazenados localmente foram removidos. "
            "Para utilizar novamente, execute /conectar."
        )

    except Exception:
        logger.exception("Erro ao desvincular usuário")

        await update.message.reply_text(
            "❌ Não foi possível desvincular sua conta."
        )


async def periodos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Por segurança, utilize /periodos em uma conversa privada com o bot."
        )
        return

    telegram_id = update.effective_user.id

    await update.message.reply_text(
        "🔎 Consultando os períodos letivos disponíveis no SUAP..."
    )

    try:
        lista = await asyncio.to_thread(
            listar_periodos,
            telegram_id
        )

        if not lista:
            await update.message.reply_text(
                "Nenhum período letivo encontrado na sua conta SUAP."
            )
            return

        mensagem = [
            "📚 *PERÍODOS LETIVOS DISPONÍVEIS*",
            ""
        ]

        for indice, item in enumerate(lista):
            ano = item["ano"]
            periodo = item["periodo"]

            if indice == 0:
                mensagem.append(
                    f"🟢 *{ano}/{periodo}* — Mais recente"
                )
            else:
                mensagem.append(
                    f"📖 {ano}/{periodo}"
                )

        mensagem.extend([
            "",
            "Para consultar suas notas:",
            "`/notas 2026 2`"
        ])

        await update.message.reply_text(
            "\n".join(mensagem),
            parse_mode="Markdown"
        )

    except ValueError as erro:
        await update.message.reply_text(
            f"🔐 {erro}"
        )

    except RuntimeError as erro:
        logger.error("Erro ao consultar períodos: %s", type(erro).__name__)

        await update.message.reply_text(
            "❌ Não foi possível consultar seus períodos letivos."
        )

    except requests.exceptions.RequestException:
        await update.message.reply_text(
            "❌ Não foi possível conectar ao SUAP."
        )

    except Exception as erro:
        logger.exception("Erro no comando /periodos")

        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado."
        )


async def notas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "Por segurança, consulte suas notas em uma conversa privada com o bot."
        )
        return

    telegram_id = update.effective_user.id

    try:
        if context.args:
            if len(context.args) != 2:
                await update.message.reply_text(
                    "Formato correto: /notas 2026 2"
                )
                return

            try:
                ano = int(context.args[0])
                periodo = int(context.args[1])

                if ano < 2000 or periodo not in (1, 2):
                    raise ValueError
            except ValueError:
                await update.message.reply_text(
                    "Informe um ano e período válidos.\n"
                    "Exemplo: /notas 2026 2"
                )
                return

        else:
            await update.message.reply_text(
                "🔎 Identificando seu período letivo mais recente..."
            )

            ano, periodo = await asyncio.to_thread(
                obter_periodo_mais_recente,
                telegram_id
            )

        await update.message.reply_text(
            f"📚 Consultando seu boletim {ano}/{periodo} no SUAP..."
        )

        disciplinas = await asyncio.to_thread(
            consultar_boletim,
            telegram_id,
            ano,
            periodo
        )

        if not disciplinas:
            await update.message.reply_text(
                "Nenhuma disciplina encontrada para esse período."
            )
            return

        mensagem = formatar_boletim(
            disciplinas,
            ano,
            periodo
        )

        partes = []
        atual = ""

        for linha in mensagem.split("\n"):
            if len(atual) + len(linha) + 1 > 4000:
                partes.append(atual)
                atual = linha
            else:
                atual += ("\n" if atual else "") + linha

        if atual:
            partes.append(atual)

        for parte in partes:
            await update.message.reply_text(
                parte,
                parse_mode="Markdown"
            )

    except ValueError as erro:
        await update.message.reply_text(
            f"🔐 {erro}"
        )

    except RuntimeError as erro:
        logger.error("Erro ao consultar períodos ou autenticação: %s", type(erro).__name__)

        await update.message.reply_text(
            "🔐 Não foi possível concluir a consulta. "
            "Verifique sua conexão com o SUAP ou execute /conectar novamente."
        )

    except requests.exceptions.HTTPError as erro:
        status_code = (
            erro.response.status_code
            if erro.response is not None
            else None
        )

        await update.message.reply_text(
            f"❌ Erro ao consultar o SUAP (HTTP {status_code})."
        )

    except requests.exceptions.RequestException:
        await update.message.reply_text(
            "❌ Não foi possível conectar ao SUAP."
        )

    except Exception as erro:
        logger.exception("Erro no comando /notas")

        await update.message.reply_text(
            "❌ Ocorreu um erro inesperado ao consultar suas notas."
        )


def main():
    if not TOKEN:
        raise ValueError("Token do Telegram não encontrado!")

    if not OAUTH_BASE_URL:
        raise ValueError("OAUTH_BASE_URL não encontrado no .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("conectar", conectar))
    app.add_handler(CommandHandler("desconectar", desconectar))
    app.add_handler(CommandHandler("notas", notas))
    app.add_handler(CommandHandler("periodos", periodos))

    logger.info("IFMG Assistant iniciado")

    app.run_polling()


if __name__ == "__main__":
    main()
