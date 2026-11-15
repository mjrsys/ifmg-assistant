import tempfile
from pathlib import Path

from database.db import (
    inicializar_banco,
    criar_estado_oauth,
    estado_oauth_existe,
    consumir_estado_oauth
)

telegram_id = 123456789

with tempfile.TemporaryDirectory() as diretorio:
    banco_teste = Path(diretorio) / "teste.db"

    inicializar_banco(banco_teste)

    # Primeiro estado
    estado1 = criar_estado_oauth(
        telegram_id,
        database_path=banco_teste
    )

    assert estado_oauth_existe(estado1, banco_teste)
    print("1. Primeiro estado criado.")

    # Segundo estado para o mesmo estudante
    estado2 = criar_estado_oauth(
        telegram_id,
        database_path=banco_teste
    )

    assert not estado_oauth_existe(estado1, banco_teste)
    assert estado_oauth_existe(estado2, banco_teste)
    print("2. Estado anterior invalidado.")

    # O segundo estado pode ser consumido apenas uma vez
    usuario = consumir_estado_oauth(estado2, banco_teste)

    assert usuario == telegram_id
    assert not estado_oauth_existe(estado2, banco_teste)
    print("3. Novo estado consumido corretamente.")

print("\nTodos os testes passaram!")
