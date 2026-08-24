import json
import os
from typing import Optional

# Tenta carregar python-dotenv se disponível; caso contrário, faz leitura nativa de fallback
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))



class Settings:
    """Configurações da aplicação lidas de variáveis de ambiente."""

    # Portal
    SITE_BASE_URL: str = os.getenv("SITE_BASE_URL", "https://portal-monitoramento.exemplo.com.br")
    SITE_LOGIN_URL: str = os.getenv("SITE_LOGIN_URL", f"{SITE_BASE_URL}/login")
    SITE_FLOWS_URL: str = os.getenv("SITE_FLOWS_URL", f"{SITE_BASE_URL}/fluxos")
    SITE_USERNAME: str = os.getenv("SITE_USERNAME", "")
    SITE_PASSWORD: str = os.getenv("SITE_PASSWORD", "")

    # Seletores CSS
    SELECTOR_USERNAME_INPUT: str = os.getenv(
        "SELECTOR_USERNAME_INPUT",
        "input[placeholder*='E-mail'], input[type='email'], input[formcontrolname='email'], input[name='username'], #usuario, #login, input[type='text']"
    )
    SELECTOR_PASSWORD_INPUT: str = os.getenv(
        "SELECTOR_PASSWORD_INPUT",
        "input[placeholder*='Senha'], input[type='password'], input[formcontrolname='password'], input[name='password'], #senha"
    )
    SELECTOR_LOGIN_BUTTON: str = os.getenv(
        "SELECTOR_LOGIN_BUTTON",
        "button:has-text('Acessar'), button[type='submit'], #btn-login, input[type='submit'], button:has-text('Entrar'), button:has-text('Login')"
    )
    # Seletores do Modal de Filtro
    SELECTOR_FILTER_OPEN_BUTTON: str = os.getenv(
        "SELECTOR_FILTER_OPEN_BUTTON",
        "button:has-text('Filtrar'), button:has(.fa-filter), [title*='Filtrar'], [aria-label*='Filtrar'], .btn-filter, .btn-filtro"
    )
    SELECTOR_MODAL_EQUIPMENT_INPUT: str = os.getenv(
        "SELECTOR_MODAL_EQUIPMENT_INPUT",
        "input[placeholder*='Equipamento'], input[aria-label*='Equipamento'], .mat-form-field:has-text('Equipamento') input, input[name='equipamento'], input[type='search'], input[type='text']"
    )
    SELECTOR_MODAL_SEARCH_BUTTON: str = os.getenv(
        "SELECTOR_MODAL_SEARCH_BUTTON",
        "button:has(.fa-search), button.btn-search, button:has-text('Buscar'), button.mat-icon-button, button.mat-fab, button:has(svg)"
    )

    # Seletores da Tabela / Grid
    SELECTOR_LANES_TABLE: str = os.getenv(
        "SELECTOR_LANES_TABLE",
        "table.tabela-fluxos, #grid-faixas, table, .mat-table, .grid-fluxos"
    )
    SELECTOR_LANE_ROWS: str = os.getenv(
        "SELECTOR_LANE_ROWS",
        "tbody tr, tr.linha-faixa, .mat-row, tr"
    )

    # Lista padrão de 23 equipamentos monitorados no projeto
    DEFAULT_EQUIPMENT_LIST: str = (
        "SPK347,SPK348,SPK351,SPK352,SBR034,SBR136,SBR185,SBR244,SBR286,SBR292,"
        "SBR298,SBR391,SBR392,SBR397,SBR399,SBR402,SBR403,SBR427,SBR506,SBR507,"
        "SBR631,SBR745,SBR816"
    )
    EQUIPMENT_LIST: str = os.getenv("EQUIPMENT_LIST", DEFAULT_EQUIPMENT_LIST)

    # Google Sheets
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", None)
    SHEET_TAB_HISTORY: str = os.getenv("SHEET_TAB_HISTORY", "Historico_Geral")
    SHEET_TAB_PENDING: str = os.getenv("SHEET_TAB_PENDING", "Pendencias_Tecnicas")

    # Execução
    HEADLESS: bool = os.getenv("HEADLESS", "True").strip().lower() in ("true", "1", "yes")
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "30000"))
    INITIAL_PAGE_WAIT_SECONDS: int = int(os.getenv("INITIAL_PAGE_WAIT_SECONDS", "10"))
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "False").strip().lower() in ("true", "1", "yes")

    @classmethod
    def get_configured_equipments(cls) -> list[str]:
        """Retorna a lista de equipamentos especificados no .env ou a lista padrão de 23 radares."""
        raw = os.getenv("EQUIPMENT_LIST", cls.EQUIPMENT_LIST) or cls.DEFAULT_EQUIPMENT_LIST
        return [item.strip() for item in raw.split(",") if item.strip()]

    @classmethod
    def get_google_credentials_dict(cls) -> Optional[dict]:
        """Retorna o dicionário de credenciais a partir do JSON no env ou do arquivo local."""
        json_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", cls.GOOGLE_SERVICE_ACCOUNT_JSON)
        if json_env:
            try:
                return json.loads(json_env)
            except Exception as e:
                raise ValueError(f"Falha ao decodificar GOOGLE_SERVICE_ACCOUNT_JSON: {e}")
        
        file_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", cls.GOOGLE_SERVICE_ACCOUNT_FILE)
        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)

        return None



settings = Settings()
