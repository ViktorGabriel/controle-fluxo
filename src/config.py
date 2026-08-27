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
    SELECTOR_EQUIPMENT_FILTER: str = os.getenv(
        "SELECTOR_EQUIPMENT_FILTER",
        "select#equipamento, select[name='equipamento'], select.filtro-equipamento, select"
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

    # Lista padrão de 60 faixas monitoradas no projeto
    DEFAULT_EQUIPMENT_LIST: str = (
        "SPK347-1,SPK347-2,SPK348-1,SPK348-2,SPK351-1,SPK351-2,SPK352-1,SPK352-2,"
        "SBR034-1,SBR034-2,SBR034-3,SBR136-1,SBR185-2,SBR185-3,SBR244-1,SBR244-2,SBR244-3,"
        "SBR286-4,SBR286-5,SBR292-1,SBR292-2,SBR292-3,SBR298-1,SBR298-2,SBR391-1,SBR391-2,SBR391-3,"
        "SBR392-1,SBR392-2,SBR392-3,SBR397-3,SBR397-4,SBR397-5,SBR399-1,SBR399-2,"
        "SBR402-1,SBR402-2,SBR402-3,SBR402-4,SBR403-1,SBR403-2,SBR403-3,SBR427-1,SBR427-2,SBR427-3,"
        "SBR506-1,SBR506-2,SBR506-3,SBR507-1,SBR507-2,SBR507-3,SBR631-1,SBR631-2,SBR631-3,"
        "SBR745-1,SBR745-2,SBR745-3,SBR816-1,SBR816-2,SBR816-3"
    )
    EQUIPMENT_LIST: str = os.getenv("EQUIPMENT_LIST", DEFAULT_EQUIPMENT_LIST)

    # Google Sheets
    GOOGLE_SHEET_ID: str = os.getenv("GOOGLE_SHEET_ID", "")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    GOOGLE_SERVICE_ACCOUNT_JSON: Optional[str] = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", None)
    SHEET_TAB_HISTORY: str = os.getenv("SHEET_TAB_HISTORY", "Historico_Geral")
    SHEET_TAB_PENDING: str = os.getenv("SHEET_TAB_PENDING", "Pendencias_Tecnicas")

    @staticmethod
    def _safe_int(env_name: str, default: int) -> int:
        val = os.getenv(env_name, "")
        if not val or not val.strip():
            return default
        try:
            return int(val.strip())
        except ValueError:
            return default

    @staticmethod
    def _safe_bool(env_name: str, default: bool) -> bool:
        val = os.getenv(env_name, "")
        if not val or not val.strip():
            return default
        return val.strip().lower() in ("true", "1", "yes")

    # Execução
    HEADLESS: bool = _safe_bool("HEADLESS", True)
    BROWSER_TIMEOUT_MS: int = _safe_int("BROWSER_TIMEOUT_MS", 30000)
    INITIAL_PAGE_WAIT_SECONDS: int = _safe_int("INITIAL_PAGE_WAIT_SECONDS", 10)
    MOCK_MODE: bool = _safe_bool("MOCK_MODE", False)
    ALLOW_MOCK_SHEETS_RECORDING: bool = _safe_bool("ALLOW_MOCK_SHEETS_RECORDING", False)

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
