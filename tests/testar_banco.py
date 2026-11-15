import tempfile
from pathlib import Path

from database.db import (
    inicializar_banco,
    salvar_tokens,
    obter_tokens,
    remover_usuario
)

telegram_id = 123456789
access = "access-token-ficticio"
refresh = "refresh-token-ficticio"

with tempfile.TemporaryDirectory() as diretorio:
    banco_teste = Path(diretorio) / "teste.db"

    inicializar_banco(banco_teste)

    # Salvar
    salvar_tokens(
        telegram_id=telegram_id,
        access_token=access,
        refresh_token=refresh,
        expires_at=1799999999,
        database_path=banco_teste
    )

    print("Tokens salvos!")

    # Recuperar
    dados = obter_tokens(telegram_id, banco_teste)

    assert dados is not None
    assert dados["access_token"] == access
    assert dados["refresh_token"] == refresh

    print("Tokens recuperados corretamente!")
    print("Tipo:", dados["token_type"])

    # Limpar o registro de teste
    remover_usuario(telegram_id, banco_teste)

    print("Registro de teste removido!")

print("\nIntegração funcionando!")
