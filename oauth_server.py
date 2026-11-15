import os
import time
import logging
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, request

from dotenv import load_dotenv
from database.db import (
    estado_oauth_existe,
    consumir_estado_oauth,
    salvar_tokens
)

load_dotenv()

app = Flask(__name__)

logging.getLogger("werkzeug").setLevel(logging.ERROR)


def validar_configuracao():
    obrigatorias = {
        "SUAP_CLIENT_ID": CLIENT_ID,
        "SUAP_CLIENT_SECRET": CLIENT_SECRET,
        "SUAP_REDIRECT_URI": REDIRECT_URI,
        "TELEGRAM_TOKEN": TELEGRAM_TOKEN,
    }

    ausentes = [
        nome
        for nome, valor in obrigatorias.items()
        if not valor
    ]

    if ausentes:
        raise RuntimeError(
            "Variáveis ausentes no .env: "
            + ", ".join(ausentes)
        )


CLIENT_ID = os.getenv("SUAP_CLIENT_ID")
CLIENT_SECRET = os.getenv("SUAP_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SUAP_REDIRECT_URI")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

AUTHORIZE_URL = "https://suap.ifmg.edu.br/o/authorize/"
TOKEN_URL = "https://suap.ifmg.edu.br/o/token/"


@app.route("/")
def home():
    return """
    <h2>IFMG Assistant</h2>
    <p>Servidor de autenticação OAuth ativo.</p>
    """


@app.route("/login")
def login():
    state = request.args.get("state")

    if not state or not estado_oauth_existe(state):
        return "Link de autenticação inválido ou expirado.", 400

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": state,
    }

    authorization_url = AUTHORIZE_URL + "?" + urlencode(params)

    return redirect(authorization_url)


def notificar_telegram(telegram_id, mensagem):
    if not TELEGRAM_TOKEN:
        raise RuntimeError("Token do Telegram não configurado.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    response = requests.post(
        url,
        json={
            "chat_id": telegram_id,
            "text": mensagem
        },
        timeout=15
    )

    response.raise_for_status()

    resultado = response.json()

    if not resultado.get("ok"):
        raise RuntimeError("Telegram não confirmou o envio.")


def notificar_cancelamento(telegram_id):
    try:
        notificar_telegram(
            telegram_id,
            "⚠️ A conexão com o SUAP não foi concluída.\n\n"
            "Você cancelou ou o SUAP recusou a autorização.\n"
            "Se desejar, execute /conectar novamente."
        )
    except Exception as erro:
        app.logger.warning(
            "Falha ao notificar cancelamento OAuth: %s",
            type(erro).__name__
        )


@app.route("/callback")
def callback():
    state = request.args.get("state")
    code = request.args.get("code")
    error = request.args.get("error")

    if not state:
        return "Estado OAuth ausente.", 400

    # Consome o estado para impedir reutilização.
    telegram_id = consumir_estado_oauth(state)

    if telegram_id is None:
        return "Autenticação inválida, expirada ou já utilizada.", 400

    if error:
        notificar_cancelamento(telegram_id)

        return """
        <h2>Conexão não concluída</h2>
        <p>A autorização do SUAP foi cancelada ou recusada.</p>
        <p>Você pode voltar ao Telegram e tentar novamente.</p>
        """, 400

    if not code:
        try:
            notificar_telegram(
                telegram_id,
                "⚠️ Não foi possível concluir sua conexão com o SUAP.\n\n"
                "O servidor não recebeu o código de autorização.\n"
                "Execute /conectar para tentar novamente."
            )
        except Exception as erro:
            app.logger.warning(
                "Falha ao notificar ausência de código OAuth: %s",
                type(erro).__name__
            )

        return """
        <h2>Conexão não concluída</h2>
        <p>Não recebemos o código de autorização do SUAP.</p>
        <p>Volte ao Telegram e tente novamente.</p>
        """, 400

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }

    try:
        response = requests.post(
            TOKEN_URL,
            data=data,
            headers={"Cache-Control": "no-cache"},
            timeout=20,
        )

        if response.status_code != 200:
            app.logger.warning(
                "Falha na troca do código OAuth. HTTP %s",
                response.status_code
            )

            try:
                notificar_telegram(
                    telegram_id,
                    "⚠️ Não foi possível conectar sua conta ao SUAP.\n\n"
                    "O servidor recusou ou não conseguiu processar a autorização.\n"
                    "Execute /conectar para tentar novamente."
                )
            except Exception as erro:
                app.logger.warning(
                    "Falha ao notificar erro OAuth: %s",
                    type(erro).__name__
                )

            if response.status_code in (400, 401):
                return (
                    "O SUAP recusou a autorização. "
                    "Tente conectar sua conta novamente pelo Telegram."
                ), 400

            return (
                "O SUAP está temporariamente indisponível. "
                "Tente novamente mais tarde."
            ), 502

        token_data = response.json()

        if "application/json" not in response.headers.get(
            "Content-Type", ""
        ).lower():
            app.logger.warning(
                "SUAP retornou conteúdo diferente de JSON."
            )
            return "Resposta inesperada do servidor SUAP.", 502

        if not isinstance(token_data, dict):
            return "Resposta OAuth inválida.", 502

        access_token = token_data.get("access_token")
        refresh_token = token_data.get("refresh_token")
        token_type = token_data.get("token_type", "Bearer")

        try:
            expires_in = int(token_data.get("expires_in", 3600))
        except (TypeError, ValueError):
            return "Tempo de expiração inválido.", 502

        if not isinstance(access_token, str) or not access_token.strip():
            return "Resposta OAuth sem token de acesso válido.", 502

        if not isinstance(refresh_token, str) or not refresh_token.strip():
            return "SUAP não retornou um refresh token válido.", 502

        if not isinstance(token_type, str) or not token_type.strip():
            return "Tipo de token inválido.", 502

        if expires_in <= 0:
            return "Tempo de expiração inválido.", 502

        expires_at = time.time() + expires_in

        salvar_tokens(
            telegram_id=telegram_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            expires_at=expires_at
        )

        try:
            notificar_telegram(
                telegram_id,
                "✅ Sua conta SUAP foi conectada com sucesso!\n\n"
                "Agora você pode consultar suas notas utilizando /notas."
            )

        except Exception as erro:
            app.logger.error(
                "Conta salva, mas a notificação falhou: %s",
                type(erro).__name__
            )

        return """
        <h2>SUAP conectado com sucesso!</h2>
        <p>Sua conta foi vinculada ao IFMG Assistant.</p>
        <p>Você já pode voltar ao Telegram.</p>
        """

    except requests.RequestException:
        app.logger.exception("Erro de comunicação com o SUAP")
        return "Erro de comunicação com o servidor do SUAP.", 502

    except (ValueError, TypeError):
        app.logger.exception("Resposta OAuth inválida")
        return "O SUAP retornou uma resposta inválida.", 502


if __name__ == "__main__":
    validar_configuracao()

    app.run(
        host="127.0.0.1",
        port=8000,
        debug=False
    )
