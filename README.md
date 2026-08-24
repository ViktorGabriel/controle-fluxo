# 🚗 Automate Visualization DailyFluxe
> Sistema automatizado para monitoramento e auditoria periódica de fluxos em radares de trânsito viário, com detecção de anomalias (status vazio/vermelho), gravação em Google Sheets e agendamento serverless via GitHub Actions.

---

## 📋 Visão Geral da Arquitetura

```mermaid
flowchart LR
    Cron[GitHub Actions\n07:50 e 13:30] -->|Dispara| Runner[Python 3.11\nPlaywright]
    Runner -->|1. Login & Filtro| Portal[Portal de Monitoramento\nde Radares]
    Runner -->|2. Identifica Falhas| Analyzer[Flow Analyzer\n(Vazio/Vermelho)]
    Analyzer -->|3. Append Rows| GSheets[Google Sheets API]
    GSheets -->|Aba Histórico & Pendências| Users[👨‍🔧 Técnicos & Equipe]
```

### Principais Recursos
* **Monitoramento Automático:** Executa 2x ao dia (às **07:50** e **13:30** no fuso de Brasília) e sob demanda.
* **Detecção Inteligente de Falhas:** Sinaliza faixas com fluxo vazio, nulo ou com destaque visual em vermelho/alerta.
* **Google Sheets com 2 Abas:**
  1. `Historico_Geral`: Auditoria completa de todas as medições.
  2. `Pendencias_Tecnicas`: Lista limpa apenas com os radares em falha para atuação do técnico.
* **Segurança e Custo Zero:** 100% serverless, sem custos de servidor e com credenciais protegidas via GitHub Secrets.

---

## ⚙️ Passo a Passo de Configuração

### 1. Configuração do Google Sheets e Conta de Serviço
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie um projeto (ex: `Monitoramento-Radares`).
3. No menu **APIs e Serviços**, ative:
   * **Google Sheets API**
   * **Google Drive API**
4. Em **IAM e Administração** $\rightarrow$ **Contas de Serviço**, clique em **Criar Conta de Serviço**.
5. Crie uma chave no formato **JSON** e baixe o arquivo para seu computador.
6. Abra a sua planilha do Google Sheets e **compartilhe com o e-mail da conta de serviço** (ex: `bot-radar@seu-projeto.iam.gserviceaccount.com`) com permissão de **Editor**.
7. Copie o **ID da Planilha** na URL do navegador:
   `https://docs.google.com/spreadsheets/d/`**`[COPIE_ESTE_ID_AQUI]`**`/edit`

---

### 2. Configuração dos Segredos no GitHub (GitHub Actions Secrets)
No seu repositório do GitHub, vá em **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions** $\rightarrow$ **New repository secret** e adicione:

| Nome do Secret | Descrição | Exemplo |
|---|---|---|
| `SITE_BASE_URL` | URL base do portal de monitoramento | `https://monitoramento.empresa.com.br` |
| `SITE_LOGIN_URL` | URL da página de login | `https://monitoramento.empresa.com.br/login` |
| `SITE_FLOWS_URL` | URL da tela de fluxos/equipamentos | `https://monitoramento.empresa.com.br/fluxos` |
| `SITE_USERNAME` | Usuário de acesso ao portal | `usuario_tecnico` |
| `SITE_PASSWORD` | Senha de acesso ao portal | `sua_senha_segura` |
| `GOOGLE_SHEET_ID` | ID da planilha do Google | `1BxiMVs0XRfwtFpo_exemplo` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Todo o conteúdo do JSON da conta de serviço | `{"type": "service_account", ...}` |

---

## 💻 Executando e Testando Localmente

### 1. Clonar o repositório e criar ambiente virtual
```bash
git clone <URL_DO_REPOSITORIO>
cd Automate-visualization-DailyFluxe

python -m venv venv
# No Windows:
.\venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate
```

### 2. Instalar dependências e navegadores
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configurar variáveis locais
Copie o arquivo de exemplo e preencha suas configurações:
```bash
cp .env.example .env
```
*(Se quiser rodar o teste com dados simulados para validar a planilha sem abrir o portal, defina `MOCK_MODE="True"` no seu `.env`)*.

### 4. Rodar os testes automatizados
```bash
pytest tests/ -v
```

### 5. Executar o robô manualmente
```bash
python main.py
```

---

## 🎯 Ajuste dos Seletores CSS do Portal
Caso o portal de trânsito possua IDs ou classes CSS específicas, você pode customizá-las diretamente no arquivo `.env` ou nas variáveis de ambiente:
* `SELECTOR_USERNAME_INPUT`: Campo de usuário.
* `SELECTOR_PASSWORD_INPUT`: Campo de senha.
* `SELECTOR_LOGIN_BUTTON`: Botão de login.
* `SELECTOR_EQUIPMENT_FILTER`: Seletor do `<select>` de filtro de equipamentos.
* `SELECTOR_LANES_TABLE` e `SELECTOR_LANE_ROWS`: Tabela e linhas com as faixas de fluxo.

---

## 🛠️ Estrutura do Código

```text
Automate-visualization-DailyFluxe/
├── .github/workflows/
│   └── daily_monitor.yml       # Orquestrador do Cron (07:50 e 13:30)
├── src/
│   ├── config.py               # Centralizador de configurações
│   ├── models.py               # Modelos Pydantic (LaneReading, EquipmentReport)
│   ├── analyzer.py             # Regras de detecção de falha (vazio/vermelho)
│   ├── scraper.py              # Automação do navegador com Playwright
│   └── sheets_service.py       # Integração com Google Sheets (gspread)
├── tests/
│   ├── test_analyzer.py        # Testes unitários das regras de falha
│   └── test_config.py          # Testes unitários de configuração
├── main.py                     # Script principal
├── requirements.txt            # Dependências
├── .env.example                # Template de configuração
└── README.md                   # Documentação do projeto
```
