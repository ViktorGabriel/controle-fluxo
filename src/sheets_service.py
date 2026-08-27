import functools
import logging
import random
import time
from typing import List, Optional, Any, Callable
from src.config import settings
from src.models import LaneReading

logger = logging.getLogger(__name__)

# Escopos necessários para acessar o Google Sheets e Google Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

HEADER_HISTORY = [
    "Data/Hora",
    "Equipamento / Radar",
    "Faixa",
    "Valor Fluxo",
    "Status",
    "Observação / Motivo"
]

HEADER_PENDING = [
    "Data/Hora",
    "Equipamento / Radar",
    "Faixa",
    "Valor Fluxo",
    "Status",
    "Motivo da Falha",
    "Ação Técnica"
]


def with_exponential_backoff(max_retries: Optional[int] = None, base_seconds: Optional[float] = None):
    """
    Decorador que executa uma função com retentativas e espera exponencial (Exponential Backoff + Jitter).
    Protege contra limites de taxa (HTTP 429), timeouts e instabilidades temporárias de rede.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retries = max_retries if max_retries is not None else settings.SHEETS_MAX_RETRIES
            base = base_seconds if base_seconds is not None else settings.SHEETS_BACKOFF_BASE_SECONDS
            
            for attempt in range(1, retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    is_last_attempt = (attempt == retries)
                    error_msg = str(e)
                    
                    if is_last_attempt:
                        logger.error(f"❌ [Google Sheets] Falha definitiva na operação '{func.__name__}' após {retries} tentativas: {error_msg}")
                        raise e
                    
                    # Calcula o tempo de espera exponencial com jitter aleatório
                    sleep_time = (base * (2 ** (attempt - 1))) + random.uniform(0.1, 0.5)
                    logger.warning(
                        f"⚠️ [Google Sheets] Tentativa {attempt}/{retries} falhou em '{func.__name__}': {error_msg}. "
                        f"Aguardando {sleep_time:.2f}s antes de tentar novamente..."
                    )
                    time.sleep(sleep_time)
        return wrapper
    return decorator


class SheetsService:
    """Gerencia a autenticação e gravação de lotes de dados no Google Sheets com resiliência a falhas."""

    def __init__(self, sheet_id: Optional[str] = None):
        self.sheet_id = sheet_id or settings.GOOGLE_SHEET_ID
        self.client: Optional[Any] = None
        self.spreadsheet: Optional[Any] = None

    @with_exponential_backoff()
    def authenticate(self) -> bool:
        """Autentica na API do Google usando o arquivo ou JSON das credenciais com retries."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            logger.error("Pacotes 'gspread' ou 'google-auth' não instalados. Execute: pip install gspread google-auth")
            return False

        creds_dict = settings.get_google_credentials_dict()
        if not creds_dict:
            logger.error("Nenhuma credencial do Google Service Account foi encontrada (.env ou JSON).")
            return False

        credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        self.client = gspread.authorize(credentials)
        self.spreadsheet = self.client.open_by_key(self.sheet_id)
        logger.info(f"Conectado com sucesso à planilha Google: '{self.spreadsheet.title}'")
        return True

    @with_exponential_backoff()
    def _get_or_create_worksheet(self, title: str, header: List[str]) -> Any:
        """Obtém uma aba existente ou cria com o cabeçalho padrão com backoff."""
        import gspread
        if not self.spreadsheet:
            raise ValueError("Spreadsheet não inicializada. Execute authenticate() primeiro.")

        try:
            worksheet = self.spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            logger.info(f"Aba '{title}' não encontrada. Criando nova aba com cabeçalho...")
            worksheet = self.spreadsheet.add_worksheet(title=title, rows=1000, cols=10)
            worksheet.append_row(header)
            return worksheet

        # Se a aba existir mas estiver totalmente vazia, insere o cabeçalho
        existing_values = worksheet.get_all_values()
        if not existing_values:
            worksheet.append_row(header)

        return worksheet

    @with_exponential_backoff()
    def _append_rows_with_backoff(self, worksheet: Any, rows: List[List[str]]) -> None:
        """Executa a inserção em lote com proteção de backoff."""
        worksheet.append_rows(rows, value_input_option="USER_ENTERED")

    def append_readings(
        self,
        all_readings: List[LaneReading],
        failed_readings: List[LaneReading]
    ) -> bool:
        """
        Insere os registros nas abas correspondentes com proteção de backoff:
        - Todas as leituras na aba de Histórico Geral
        - Apenas as falhas na aba de Pendências Técnicas
        """
        if not self.spreadsheet:
            try:
                if not self.authenticate():
                    logger.error("Abortando gravação na planilha: falha na autenticação.")
                    return False
            except Exception as e:
                logger.error(f"Erro persistente na autenticação do Google Sheets: {e}")
                return False

        try:
            # 1. Gravação no Histórico Geral
            if all_readings:
                ws_history = self._get_or_create_worksheet(settings.SHEET_TAB_HISTORY, HEADER_HISTORY)
                history_rows = [r.to_history_row() for r in all_readings]
                self._append_rows_with_backoff(ws_history, history_rows)
                logger.info(f"Gravadas {len(history_rows)} linhas no '{settings.SHEET_TAB_HISTORY}'.")

            # 2. Gravação nas Pendências Técnicas (apenas falhas)
            if failed_readings:
                ws_pending = self._get_or_create_worksheet(settings.SHEET_TAB_PENDING, HEADER_PENDING)
                pending_rows = [r.to_pending_row() for r in failed_readings]
                self._append_rows_with_backoff(ws_pending, pending_rows)
                logger.info(f"🚨 Gravadas {len(pending_rows)} falhas no '{settings.SHEET_TAB_PENDING}'.")
            else:
                logger.info("Nenhuma falha detectada nesta execução para a aba de Pendências.")

            return True
        except Exception as e:
            logger.error(f"Erro ao gravar linhas no Google Sheets após retentativas: {e}")
            return False
