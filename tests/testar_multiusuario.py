import sqlite3
import tempfile
from pathlib import Path

from database.db import (
    inicializar_banco,
    salvar_tokens,
    obter_tokens,
    remover_usuario
)

# IDs fictícios.
aluno_1 = 987654321
aluno_2 = 987654322

with tempfile.TemporaryDirectory() as diretorio:
    banco_teste = Path(diretorio) / "teste.db"

    inicializar_banco(banco_teste)

    try:
        # Cadastra dois estudantes.
        salvar_tokens(
            aluno_1,
            "access-aluno-1",
            "refresh-aluno-1",
            database_path=banco_teste
        )

        salvar_tokens(
            aluno_2,
            "access-aluno-2",
            "refresh-aluno-2",
            database_path=banco_teste
        )

        # Recupera os dados individualmente.
        dados_1 = obter_tokens(aluno_1, banco_teste)
        dados_2 = obter_tokens(aluno_2, banco_teste)

        assert dados_1 is not None
        assert dados_2 is not None

        assert dados_1["access_token"] == "access-aluno-1"
        assert dados_2["access_token"] == "access-aluno-2"

        assert dados_1["refresh_token"] == "refresh-aluno-1"
        assert dados_2["refresh_token"] == "refresh-aluno-2"

        # Confirma que os tokens não estão em texto puro.
        with sqlite3.connect(banco_teste) as conn:
            registro = conn.execute(
                "SELECT suap_access_token FROM usuarios WHERE telegram_id = ?",
                (aluno_1,)
            ).fetchone()

        assert registro is not None
        assert registro[0] != "access-aluno-1"

        print("1. Dois estudantes cadastrados.")
        print("2. Tokens recuperados individualmente.")
        print("3. Isolamento entre contas confirmado.")
        print("4. Tokens armazenados criptografados.")

    finally:
        remover_usuario(aluno_1, banco_teste)
        remover_usuario(aluno_2, banco_teste)

print("\nTodos os testes passaram!")
