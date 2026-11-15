
import os
import time
import requests
import threading


from dotenv import load_dotenv
from database.db import obter_tokens, salvar_tokens

load_dotenv()

BASE_URL = "https://suap.ifmg.edu.br"
TOKEN_URL = f"{BASE_URL}/o/token/"

CLIENT_ID = os.getenv("SUAP_CLIENT_ID")
CLIENT_SECRET = os.getenv("SUAP_CLIENT_SECRET")
# Bloqueios individuais para renovação de tokens.
_lock_usuarios = {}
_lock_usuarios_guard = threading.Lock()


def obter_lock_usuario(telegram_id):
    with _lock_usuarios_guard:
        if telegram_id not in _lock_usuarios:
            _lock_usuarios[telegram_id] = threading.Lock()

        return _lock_usuarios[telegram_id]



def renovar_token(telegram_id, tokens):
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        raise RuntimeError(
            "Não existe refresh_token. É necessário conectar novamente ao SUAP."
        )

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Cache-Control": "no-cache"},
        timeout=20
    )

    response.raise_for_status()
    novos_tokens = response.json()

    access_token = novos_tokens.get("access_token")

    if not access_token:
        raise RuntimeError("O SUAP não retornou um novo access_token.")

    novo_refresh = novos_tokens.get("refresh_token") or refresh_token

    expires_in = int(novos_tokens.get("expires_in", 3600))
    expires_at = time.time() + expires_in

    salvar_tokens(
        telegram_id=telegram_id,
        access_token=access_token,
        refresh_token=novo_refresh,
        token_type=novos_tokens.get(
            "token_type",
            tokens.get("token_type", "Bearer")
        ),
        expires_at=expires_at
    )

    return {
        "access_token": access_token,
        "refresh_token": novo_refresh,
        "token_type": novos_tokens.get(
            "token_type",
            tokens.get("token_type", "Bearer")
        ),
        "expires_at": expires_at
    }


def obter_token_sincronizado(
    telegram_id,
    token_usado=None,
    forcar_renovacao=False
):
    lock = obter_lock_usuario(telegram_id)

    with lock:
        # Busca novamente os tokens diretamente do banco.
        tokens = obter_tokens(telegram_id)

        if tokens is None:
            raise ValueError(
                "Conta SUAP não conectada. Utilize /conectar."
            )

        if not CLIENT_ID or not CLIENT_SECRET:
            raise RuntimeError(
                "Credenciais OAuth não configuradas."
            )

        # Outra operação já renovou o token.
        if (
            token_usado is not None
            and tokens["access_token"] != token_usado
        ):
            return tokens

        expires_at = tokens.get("expires_at")

        precisa_renovar = (
            expires_at is not None
            and expires_at <= time.time() + 60
        )

        if forcar_renovacao or precisa_renovar:
            tokens = renovar_token(telegram_id, tokens)

        return tokens

def obter_token_valido(telegram_id):
    return obter_token_sincronizado(telegram_id)

def consultar_boletim(telegram_id, ano, periodo):
    tokens = obter_token_valido(telegram_id)

    url = (
        f"{BASE_URL}/api/v2/minhas-informacoes/"
        f"boletim/{ano}/{periodo}/"
    )

    headers = {
        "Authorization": (
            f"{tokens['token_type']} {tokens['access_token']}"
        ),
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    # Se o SUAP rejeitar o token, tenta renovar uma vez.
    if response.status_code == 401:
        tokens = obter_token_sincronizado(
            telegram_id,
            token_usado=tokens["access_token"],
            forcar_renovacao=True
        )

    response.raise_for_status()

    return response.json()

def listar_periodos(telegram_id):
    tokens = obter_token_valido(telegram_id)

    url = (
        f"{BASE_URL}/api/v2/minhas-informacoes/"
        "meus-periodos-letivos/"
    )

    headers = {
        "Authorization": (
            f"{tokens['token_type']} {tokens['access_token']}"
        ),
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    if response.status_code == 401:
        tokens = obter_token_sincronizado(
            telegram_id,
            token_usado=tokens["access_token"],
            forcar_renovacao=True
        )

    response.raise_for_status()

    dados = response.json()

    if not isinstance(dados, list):
        raise RuntimeError("Formato inesperado dos períodos letivos.")

    periodos = []

    for item in dados:
        try:
            ano = int(item["ano_letivo"])
            periodo = int(item["periodo_letivo"])
        except (KeyError, TypeError, ValueError):
            continue

        if ano > 0 and periodo in (1, 2):
            periodos.append({
                "ano": ano,
                "periodo": periodo
            })

    return sorted(
        periodos,
        key=lambda x: (x["ano"], x["periodo"]),
        reverse=True
    )


def obter_periodo_mais_recente(telegram_id):
    periodos = listar_periodos(telegram_id)

    if not periodos:
        raise RuntimeError("Nenhum período letivo encontrado no SUAP.")

    return periodos[0]["ano"], periodos[0]["periodo"]

def verificar_conexao_suap(telegram_id):
    tokens = obter_token_valido(telegram_id)

    url = (
        f"{BASE_URL}/api/v2/minhas-informacoes/"
        "meus-dados/"
    )

    headers = {
        "Authorization": (
            f"{tokens['token_type']} {tokens['access_token']}"
        ),
        "Accept": "application/json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    # Se o SUAP rejeitar o token, tenta renovar uma vez.
    if response.status_code == 401:
        tokens = renovar_token(telegram_id, tokens)

        headers["Authorization"] = (
            f"{tokens['token_type']} {tokens['access_token']}"
        )

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

    if response.status_code == 401:
        return False

    response.raise_for_status()

    return response.status_code == 200



def formatar_boletim(disciplinas, ano, periodo):
    mensagem = [
        f"📚 *Boletim — {ano}/{periodo}*",
        f"Total de disciplinas: {len(disciplinas)}",
        ""
    ]

    for materia in disciplinas:
        mensagem.append(f"📖 *{materia['disciplina']}*")

        for etapa in range(1, 5):
            dados = materia.get(f"nota_etapa_{etapa}") or {}
            nota = dados.get("nota")

            valor = formatar_nota(nota)

            mensagem.append(
                f"  • Etapa {etapa}: {valor}"
            )

        media = materia.get("media_disciplina")
        mensagem.append(
            f"  • Média: {formatar_nota(media)}"
        )

        faltas = materia.get("numero_faltas", 0)
        mensagem.append(f"  • Faltas: {faltas}")

        frequencia = materia.get(
            "percentual_carga_horaria_frequentada"
        )

        if frequencia is not None:
            mensagem.append(
                f"  • Frequência: {frequencia:.2f}%"
            )

        situacao = materia.get("situacao", "N/D")
        mensagem.append(f"  • Situação: {situacao}")

        mensagem.append("")

    return "\n".join(mensagem)


def formatar_nota(valor):
    if valor is None:
        return "Não lançada"

    return f"{valor / 10:.1f}".replace(".", ",")
