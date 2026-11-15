import tempfile
from pathlib import Path

from database.db import (
    inicializar_banco,
    salvar_tokens,
    obter_tokens,
    criar_estado_oauth,
    estado_oauth_existe,
    remover_usuario
)

telegram_id = 987654321

with tempfile.TemporaryDirectory() as diretorio:
    banco_teste = Path(diretorio) / "teste.db"

    inicializar_banco(banco_teste)

    salvar_tokens(
        telegram_id=telegram_id,
        access_token="token_teste",
        refresh_token="refresh_teste",
        database_path=banco_teste
    )

    estado = criar_estado_oauth(
        telegram_id,
        database_path=banco_teste
    )

    assert obter_tokens(telegram_id, banco_teste) is not None
    assert estado_oauth_existe(estado, banco_teste)

    print("1. Tokens e estado OAuth criados.")

    remover_usuario(telegram_id, banco_teste)

    assert obter_tokens(telegram_id, banco_teste) is None
    assert not estado_oauth_existe(estado, banco_teste)

    print("2. Tokens removidos.")
    print("3. Estado OAuth invalidado.")

print("\nTodos os testes passaram!")
