import threading
import time
from concurrent.futures import ThreadPoolExecutor

import suap


telegram_id = 987654321

# Simula o armazenamento compartilhado.
tokens_armazenados = {
    "access_token": "access_teste",
    "refresh_token": "refresh_teste",
    "token_type": "Bearer",
    "expires_at": time.time() + 3600
}

contador = 0
contador_lock = threading.Lock()


def obter_tokens_simulado(usuario):
    return tokens_armazenados.copy()


def renovar_simulado(usuario, tokens):
    global contador

    with contador_lock:
        contador += 1

    time.sleep(1)

    novos = tokens.copy()
    novos["access_token"] = "access_renovado"
    novos["refresh_token"] = "refresh_renovado"
    novos["expires_at"] = time.time() + 3600

    # Simula a atualização no banco.
    tokens_armazenados.update(novos)

    return novos


suap.obter_tokens = obter_tokens_simulado
suap.renovar_token = renovar_simulado

suap.CLIENT_ID = "teste"
suap.CLIENT_SECRET = "teste"


def executar():
    return suap.obter_token_sincronizado(
        telegram_id,
        token_usado="access_teste",
        forcar_renovacao=True
    )


with ThreadPoolExecutor(max_workers=5) as executor:
    resultados = list(
        executor.map(lambda _: executar(), range(5))
    )


assert contador == 1, f"Foram realizadas {contador} renovações!"

assert all(
    resultado["access_token"] == "access_renovado"
    for resultado in resultados
)

print("1. Cinco operações executadas simultaneamente.")
print("2. Apenas uma renovação foi realizada.")
print("3. Todas receberam o token atualizado.")

print("\nTodos os testes passaram!")
