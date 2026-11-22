# OrdemPro — Sistema Web de Ordem de Serviço

Projeto acadêmico de desenvolvimento de software com Python, Flask, SQLite, HTML, CSS e Bootstrap.

## Funcionalidades da primeira versão
- Autenticação de administrador
- Cadastro de clientes e técnicos
- Abertura e consulta de ordens de serviço
- Atribuição de técnico, prioridade e prazo
- Atualização de status e registro de histórico
- Agenda semanal de ordens por prazo
- Valores de serviço e controle de pagamentos parciais por ordem
- Histórico de pagamentos com data e forma de pagamento
- Resumo financeiro de valores orçados, recebidos e a receber
- Atualização de nome, e-mail e senha nas Configurações
- Painel com indicadores e relatórios resumidos

## Requisitos
- Python 3.10 ou superior
- Navegador atualizado
- Acesso à internet para carregar o Bootstrap via CDN (pode ser substituído por arquivos locais)

## Instalação no Windows
```powershell
cd ordempro
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Em outro terminal/navegador, abra `http://127.0.0.1:5000/setup` uma única vez para inicializar o banco e criar o usuário inicial. Depois acesse `http://127.0.0.1:5000/login`.

**Acesso inicial de demonstração**
- E-mail: `admin@ordempro.local`
- Senha: `Admin@123`

Altere a senha e a `SECRET_KEY` antes de qualquer implantação real. A rota `/setup` é apenas para inicialização local e deve ser removida ou protegida em produção.

## Observação acadêmica
Esta é uma primeira versão funcional para servir de base ao desenvolvimento e à validação. Antes de afirmar no artigo que o produto está concluído, execute testes, registre evidências reais das telas e documente os resultados observados. Não publique dados pessoais reais durante os testes.
