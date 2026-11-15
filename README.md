# IFMG Assistant

Bot para Telegram desenvolvido em Python, integrado ao SUAP, que permite aos estudantes consultar informações acadêmicas de maneira prática e segura.

O projeto utiliza autenticação OAuth 2.0, armazenamento individualizado de credenciais e criptografia dos tokens de acesso.

> **Aviso:** Este é um projeto independente, desenvolvido para fins educacionais e de portfólio. Não é um produto oficial do Instituto Federal de Minas Gerais (IFMG).

## Funcionalidades

- **Autenticação SUAP:** conexão de contas por OAuth 2.0.
- **Consulta de notas:** acesso às informações acadêmicas do estudante.
- **Consulta de períodos:** consulta dos períodos acadêmicos.
- **Gerenciamento de contas:** conexão e desconexão individual de usuários.
- **Multiusuário:** armazenamento separado das credenciais de cada estudante.
- **Criptografia:** proteção dos tokens utilizando Fernet.
- **Renovação de tokens:** gerenciamento da renovação de credenciais.
- **Monitoramento:** comando de status para verificar o funcionamento do serviço.
- **Backup:** cópias de segurança do banco SQLite.

## Tecnologias utilizadas

- Python 3.13
- Telegram Bot API
- python-telegram-bot
- Flask
- OAuth 2.0
- SQLite
- Cryptography (Fernet)
- Requests
- python-dotenv
- Linux / Debian

## Arquitetura

O projeto é dividido em módulos:

| Arquivo ou diretório | Responsabilidade |
|---|---|
| `bot.py` | Interface e comandos do Telegram |
| `oauth_server.py` | Servidor de autenticação OAuth |
| `suap.py` | Comunicação com a API do SUAP |
| `database/` | Persistência de dados e gerenciamento de usuários |
| `security/` | Criptografia dos tokens |
| `backup.py` | Criação e validação de backups |
| `tests/` | Testes automatizados |
| `.env.example` | Modelo de configuração |

## Pré-requisitos

- Python 3.13 ou superior.
- Git.
- Token de um bot criado pelo Telegram BotFather.
- Credenciais de uma aplicação OAuth registrada no SUAP.
- Ambiente Linux recomendado para a execução do servidor.

## Instalação

Clone o repositório:

```bash
git clone https://github.com/mjrsys/ifmg-assistant.git
cd ifmg-assistant
```

Crie um ambiente virtual:

```bash
python3 -m venv venv
```

Ative o ambiente:

```bash
source venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## Configuração

Crie seu arquivo de ambiente:

```bash
cp .env.example .env
```

Configure as seguintes variáveis:

| Variável | Descrição |
|---|---|
| `TELEGRAM_TOKEN` | Token do bot do Telegram |
| `SUAP_CLIENT_ID` | Identificador da aplicação OAuth |
| `SUAP_CLIENT_SECRET` | Segredo da aplicação OAuth |
| `SUAP_REDIRECT_URI` | URI de redirecionamento cadastrada no SUAP |
| `OAUTH_BASE_URL` | Endereço base utilizado pelo bot para acessar o servidor OAuth |
| `TOKEN_ENCRYPTION_KEY` | Chave utilizada para criptografar os tokens |

Gere uma chave Fernet:

```bash
venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copie o resultado para `TOKEN_ENCRYPTION_KEY` no arquivo `.env`.

**Importante:** mantenha o `.env` e a chave de criptografia protegidos. Nunca publique credenciais, tokens ou bancos de dados com informações reais.

## Execução

O bot e o servidor OAuth são processos separados.

Terminal 1 — servidor OAuth:

```bash
venv/bin/python oauth_server.py
```

Terminal 2 — bot Telegram:

```bash
venv/bin/python bot.py
```

O servidor OAuth utiliza inicialmente `127.0.0.1:8000`.

Para permitir o acesso ao fluxo OAuth a partir de outro dispositivo, é necessário configurar um meio de acesso adequado, como um túnel SSH ou uma infraestrutura HTTPS com proxy reverso.

## Comandos disponíveis

| Comando | Descrição |
|---|---|
| `/start` | Apresentação e início |
| `/status` | Verificação do funcionamento |
| `/conectar` | Conectar conta SUAP |
| `/desconectar` | Desconectar conta SUAP |
| `/notas` | Consultar notas |
| `/periodos` | Consultar períodos acadêmicos |

## Testes automatizados

Os testes estão organizados no diretório `tests/`.

Execute individualmente:

```bash
venv/bin/python -m tests.testar_banco
venv/bin/python -m tests.testar_desconectar
venv/bin/python -m tests.testar_multiusuario
venv/bin/python -m tests.testar_oauth_states
venv/bin/python -m tests.testar_concorrencia
venv/bin/python -m tests.testar_criptografia
```

Os testes utilizam dados fictícios e bancos temporários para evitar alterações no banco de dados principal.

## Segurança

O projeto implementa mecanismos de proteção, incluindo:

- Criptografia dos tokens de acesso e atualização.
- Separação dos dados por usuário do Telegram.
- Estados OAuth com utilização única e expiração.
- Controle de concorrência durante a renovação de tokens.
- Proteção de credenciais por variáveis de ambiente.
- Backups com validação de integridade.

## Melhorias futuras

- Interface com mais informações acadêmicas.
- Notificações automáticas sobre atualizações.
- Melhorias no monitoramento e observabilidade.
- Implantação com HTTPS e infraestrutura de produção.
- Ampliação da cobertura de testes.

## Licença
Este projeto está licenciado sob a licença [MIT](LICENSE).
