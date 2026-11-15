import os
import sqlite3
from pathlib import Path
from datetime import datetime
import logging

BASE_DIR = Path(__file__).resolve().parent

BANCO_ORIGEM = BASE_DIR / "database" / "ifmg_assistant.db"
PASTA_BACKUPS = BASE_DIR / "backups"

RETENCAO = 30

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def realizar_backup():
    if not BANCO_ORIGEM.exists():
        raise FileNotFoundError("Banco de dados não encontrado.")

    PASTA_BACKUPS.mkdir(exist_ok=True)
    os.chmod(PASTA_BACKUPS, 0o700)

    horario = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino = PASTA_BACKUPS / f"ifmg-assistant_{horario}.db"

    try:
        with sqlite3.connect(BANCO_ORIGEM) as origem:
            with sqlite3.connect(destino) as backup:
                origem.backup(backup)

        with sqlite3.connect(destino) as conexao:

            resultado = conexao.execute(
                "PRAGMA integrity_check"
            ).fetchone()

        if not resultado or resultado[0] != "ok":
            raise RuntimeError("Falha na integridade do backup.")

        os.chmod(destino, 0o600)
        logging.info("Backup validado: %s", destino)

        aplicar_retencao()

    except Exception:
        destino.unlink(missing_ok=True)
        logging.exception("Erro ao realizar backup.")
        raise


def aplicar_retencao():
    arquivos = sorted(
        PASTA_BACKUPS.glob("ifmg-assistant_*.db"),
        key=lambda arquivo: arquivo.name,
        reverse=True
    )

    for arquivo in arquivos[RETENCAO:]:
        arquivo.unlink()
        logging.info("Backup antigo removido: %s", arquivo.name)


if __name__ == "__main__":
    realizar_backup()
