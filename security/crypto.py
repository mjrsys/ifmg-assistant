import os

from dotenv import load_dotenv
from cryptography.fernet import Fernet

load_dotenv()


def obter_fernet(chave=None):
    chave = chave or os.getenv("TOKEN_ENCRYPTION_KEY")

    if not chave:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY não encontrada no arquivo .env"
        )

    return Fernet(chave.encode() if isinstance(chave, str) else chave)


def criptografar(valor: str, chave=None) -> str:
    fernet = obter_fernet(chave)
    return fernet.encrypt(valor.encode()).decode()


def descriptografar(valor: str, chave=None) -> str:
    fernet = obter_fernet(chave)
    return fernet.decrypt(valor.encode()).decode()
