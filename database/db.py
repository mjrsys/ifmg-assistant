import secrets
import time
import sqlite3
from pathlib import Path

from security.crypto import criptografar, descriptografar

DATABASE_PATH = Path(__file__).parent / "ifmg_assistant.db"

def conectar(database_path=None):
    caminho = database_path or DATABASE_PATH
    conn = sqlite3.connect(caminho)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_banco(database_path=None):
    with conectar(database_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                telegram_id INTEGER PRIMARY KEY,
                suap_access_token TEXT NOT NULL,
                suap_refresh_token TEXT,
                token_type TEXT DEFAULT 'Bearer',
                expires_at REAL,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_states (
                state TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                criado_em REAL NOT NULL
            )
        """)


def salvar_tokens(
    telegram_id,
    access_token,
    refresh_token,
    token_type="Bearer",
    expires_at=None,
    database_path=None
):
    access_criptografado = criptografar(access_token)

    refresh_criptografado = (
        criptografar(refresh_token) if refresh_token else None
    )

    with conectar(database_path) as conn:
        conn.execute("""
            INSERT INTO usuarios (
                telegram_id,
                suap_access_token,
                suap_refresh_token,
                token_type,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?)

            ON CONFLICT(telegram_id) DO UPDATE SET
                suap_access_token = excluded.suap_access_token,
                suap_refresh_token = COALESCE(
                    excluded.suap_refresh_token,
                    usuarios.suap_refresh_token
                ),
		),
                token_type = excluded.token_type,
                expires_at = excluded.expires_at,
                atualizado_em = CURRENT_TIMESTAMP
        """, (
            telegram_id,
            access_criptografado,
            refresh_criptografado,
            token_type,
            expires_at
        ))

def obter_tokens(telegram_id, database_path=None):
    with conectar(database_path) as conn:        usuario = conn.execute("""
            SELECT * FROM usuarios
            WHERE telegram_id = ?
        """, (telegram_id,)).fetchone()

    if usuario is None:
        return None

    return {
        "access_token": descriptografar(
            usuario["suap_access_token"]
        ),
        "refresh_token": (
            descriptografar(usuario["suap_refresh_token"])
            if usuario["suap_refresh_token"]
            else None
        ),
        "token_type": usuario["token_type"],
        "expires_at": usuario["expires_at"]
    }


def remover_usuario(telegram_id, database_path=None):
    with conectar(database_path) as conn:

        # Remove os tokens do estudante.
        conn.execute(
            """
            DELETE FROM usuarios
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        )

        # Remove estados OAuth pendentes.
        conn.execute(
            """
            DELETE FROM oauth_states
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        )

if __name__ == "__main__":
    inicializar_banco()
    print("Banco de dados inicializado com sucesso!")


def criar_estado_oauth(telegram_id, database_path=None):
    import secrets
    import time

    state = secrets.token_urlsafe(32)
    agora = time.time()

    with conectar(database_path) as conn:

        # Remove estados expirados.
        conn.execute(
            """
            DELETE FROM oauth_states
            WHERE criado_em < ?
            """,
            (agora - 600,)
        )

        # Invalida solicitações anteriores deste estudante.
        conn.execute(
            """
            DELETE FROM oauth_states
            WHERE telegram_id = ?
            """,
            (telegram_id,)
        )

        # Cria o novo estado OAuth.
        conn.execute(
            """
            INSERT INTO oauth_states (state, telegram_id, criado_em)
            VALUES (?, ?, ?)
            """,
            (state, telegram_id, agora)
        )

    return state

def consumir_estado_oauth(state, database_path=None):
    agora = time.time()
    conn = conectar(database_path)

    try:
        conn.execute("BEGIN IMMEDIATE")

        registro = conn.execute("""
            SELECT telegram_id, criado_em
            FROM oauth_states
            WHERE state = ?
        """, (state,)).fetchone()

        # Exclui o estado independentemente de ser válido.
        conn.execute(
            "DELETE FROM oauth_states WHERE state = ?",
            (state,)
        )

        conn.commit()

        if registro is None:
            return None

        if agora - registro["criado_em"] > 600:
            return None

        return registro["telegram_id"]

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def estado_oauth_existe(state, database_path=None):
    agora = time.time()

    with conectar(database_path) as conn:
        registro = conn.execute("""
            SELECT criado_em
            FROM oauth_states
            WHERE state = ?
        """, (state,)).fetchone()

    if registro is None:
        return False

    return agora - registro["criado_em"] <= 600
