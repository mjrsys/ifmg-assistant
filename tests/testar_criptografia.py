from cryptography.fernet import Fernet
from security.crypto import criptografar, descriptografar

# Chave exclusiva para este teste
chave_teste = Fernet.generate_key()

texto_original = "token-de-teste-123"

texto_criptografado = criptografar(
    texto_original,
    chave=chave_teste
)

texto_descriptografado = descriptografar(
    texto_criptografado,
    chave=chave_teste
)

assert texto_original == texto_descriptografado
assert texto_original not in texto_criptografado

print("1. Texto criptografado.")
print("2. Texto descriptografado corretamente.")
print("3. Conteúdo original não aparece no texto criptografado.")

print("\nCriptografia funcionando!")
