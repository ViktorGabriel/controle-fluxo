import logging
from datetime import datetime
from typing import List, Optional, Any
from src.config import settings
from src.models import EquipmentReport, LaneReading, ScanSummary, StatusEnum
from src.analyzer import FlowAnalyzer

logger = logging.getLogger(__name__)


class PortalScraper:
    """Gerencia a automação no navegador com Playwright para extração dos dados de fluxo."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Any] = None
        self.page: Optional[Any] = None


    def _get_current_timestamp(self) -> str:
        """Retorna a data e hora atual formatada no padrão brasileiro."""
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    def start_browser(self):
        """Inicializa o navegador Playwright."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Playwright não instalado. Execute: pip install playwright && playwright install chromium"
            )

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=settings.HEADLESS,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        self.page = self.browser.new_page()
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)
        logger.info(f"Navegador Playwright iniciado (Headless={settings.HEADLESS}).")


    def close_browser(self):
        """Encerra as instâncias do navegador de forma segura."""
        try:
            if self.page:
                self.page.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Navegador encerrado.")
        except Exception as e:
            logger.warning(f"Erro ao fechar navegador: {e}")

    def login(self) -> bool:
        """Efetua login no portal utilizando as credenciais configuradas."""
        if not self.page:
            raise RuntimeError("Navegador não inicializado.")

        logger.info(f"Acessando tela de login: {settings.SITE_LOGIN_URL}")
        try:
            self.page.goto(settings.SITE_LOGIN_URL, wait_until="networkidle")

            # Preenchimento de usuário e senha
            logger.info("Preenchendo credenciais de acesso...")
            self.page.fill(settings.SELECTOR_USERNAME_INPUT, settings.SITE_USERNAME)
            self.page.fill(settings.SELECTOR_PASSWORD_INPUT, settings.SITE_PASSWORD)

            # Clique no botão de login
            with self.page.expect_navigation(wait_until="networkidle", timeout=settings.BROWSER_TIMEOUT_MS):
                self.page.click(settings.SELECTOR_LOGIN_BUTTON)

            logger.info("Login efetuado com sucesso!")
            return True
        except PlaywrightTimeoutError:
            logger.error("Timeout durante o processo de login.")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado durante o login: {e}")
            return False

    def get_equipment_list(self) -> List[str]:
        """Obtém a lista de equipamentos disponíveis no menu/select de filtro."""
        if not self.page:
            return []

        try:
            # Aguarda o elemento de filtro estar visível
            self.page.wait_for_selector(settings.SELECTOR_EQUIPMENT_FILTER, state="visible")
            
            # Extrai os textos ou valores das opções do select
            options = self.page.eval_on_selector_all(
                f"{settings.SELECTOR_EQUIPMENT_FILTER} option",
                "elements => elements.map(e => e.value || e.innerText).filter(v => v && v.trim() !== '')"
            )
            
            # Remove duplicidades mantendo ordem
            unique_options = list(dict.fromkeys([opt.strip() for opt in options if opt.strip()]))
            logger.info(f"Detectados {len(unique_options)} equipamentos no filtro do portal.")
            return unique_options
        except Exception as e:
            logger.warning(f"Não foi possível obter lista automática do select: {e}. Usando fallback.")
            return []

    def scrape_equipment_lanes(self, equipment_id: str, timestamp: str) -> EquipmentReport:
        """Aplica o filtro para um equipamento e extrai a tabela de faixas correspondente."""
        if not self.page:
            return EquipmentReport(equipment_id=equipment_id, error_message="Página não inicializada")

        logger.info(f"Verificando equipamento: {equipment_id}")
        report = EquipmentReport(equipment_id=equipment_id)

        try:
            # 1. Aplica o filtro do equipamento selecionado
            self.page.select_option(settings.SELECTOR_EQUIPMENT_FILTER, value=equipment_id)
            
            # Aguarda a atualização da tabela de dados
            self.page.wait_for_selector(settings.SELECTOR_LANES_TABLE, state="visible")
            self.page.wait_for_timeout(1000)  # Pequena pausa para garantir renderização dos estilos/cores

            # 2. Localiza as linhas da tabela de faixas
            rows = self.page.query_selector_all(settings.SELECTOR_LANE_ROWS)
            if not rows:
                logger.warning(f"Nenhuma linha encontrada na tabela para o equipamento {equipment_id}")
                report.error_message = "Tabela vazia ou não carregada"
                return report

            for idx, row in enumerate(rows, start=1):
                # Extrai as células (colunas) da linha
                cells = row.query_selector_all("td, th")
                if not cells:
                    continue

                # Coluna 1: Nome/Faixa (ex: Faixa 1, Faixa 2)
                lane_name = cells[0].inner_text().strip() if len(cells) > 0 else f"Faixa {idx}"
                
                # Coluna 2 (ou última): Valor do fluxo
                value_cell = cells[1] if len(cells) > 1 else cells[0]
                raw_val = value_cell.inner_text().strip()

                # Verifica classes e estilos de cor vermelha na célula ou na linha
                row_class = row.get_attribute("class") or ""
                cell_class = value_cell.get_attribute("class") or ""
                cell_style = value_cell.get_attribute("style") or ""
                
                is_red = FlowAnalyzer.is_red_style(f"{row_class} {cell_class}", cell_style)

                # Classifica a leitura
                reading = FlowAnalyzer.evaluate_reading(
                    timestamp=timestamp,
                    equipment_id=equipment_id,
                    lane_number=lane_name,
                    raw_value=raw_val,
                    is_red_highlighted=is_red
                )
                report.readings.append(reading)

            report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
            return report

        except PlaywrightTimeoutError:
            logger.error(f"Timeout ao carregar dados do equipamento {equipment_id}")
            report.error_message = "Timeout de carregamento"
            return report
        except Exception as e:
            logger.error(f"Erro ao extrair equipamento {equipment_id}: {e}")
            report.error_message = str(e)
            return report

    def run_full_scan(self) -> ScanSummary:
        """Executa o ciclo completo de escaneamento de todos os equipamentos."""
        if settings.MOCK_MODE:
            logger.info("Modo MOCK ativado: gerando dados simulados para teste.")
            return self.generate_mock_data()

        timestamp = self._get_current_timestamp()
        summary = ScanSummary(execution_time=timestamp)

        try:
            self.start_browser()
            if not self.login():
                logger.error("Interrompendo escaneamento devido a falha no login.")
                return summary

            # Navega até a página de fluxos se for diferente da URL pós-login
            if settings.SITE_FLOWS_URL and settings.SITE_FLOWS_URL != self.page.url:
                self.page.goto(settings.SITE_FLOWS_URL, wait_until="networkidle")

            equipments = self.get_equipment_list()
            if not equipments:
                logger.warning("Nenhum equipamento retornado pelo portal.")
                return summary

            for equip in equipments:
                rep = self.scrape_equipment_lanes(equip, timestamp)
                summary.reports.append(rep)

            summary.total_equipments = len(summary.reports)
            summary.total_lanes = len(summary.all_readings)
            summary.total_failures = len(summary.failed_readings)
            return summary

        finally:
            self.close_browser()

    def generate_mock_data(self) -> ScanSummary:
        """Gera dados simulados para validação local e em ambiente de CI/CD sem portal real."""
        timestamp = self._get_current_timestamp()
        summary = ScanSummary(execution_time=timestamp)

        mock_equipments = [
            ("RADAR-AV-BRASIL-KM12", [("Faixa 1", "1420", False), ("Faixa 2", "1380", False)]),
            ("RADAR-AV-PAULISTA-N200", [("Faixa 1", "", True), ("Faixa 2", "950", False)]),  # Faixa 1 com Falha (Vazio + Vermelho)
            ("RADAR-ROD-ANCHIETA-KM18", [("Faixa 1", "0", True), ("Faixa 2", "1120", False)]),  # Faixa 1 Falha (Zerado + Vermelho)
            ("RADAR-MARGINAL-TIETE-04", [("Faixa 1", "1850", False), ("Faixa 2", "1790", False), ("Faixa 3", "1640", False)])
        ]

        for eq_id, lanes in mock_equipments:
            report = EquipmentReport(equipment_id=eq_id)
            for l_name, val, is_red in lanes:
                reading = FlowAnalyzer.evaluate_reading(
                    timestamp=timestamp,
                    equipment_id=eq_id,
                    lane_number=l_name,
                    raw_value=val,
                    is_red_highlighted=is_red
                )
                report.readings.append(reading)
            report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
            summary.reports.append(report)

        summary.total_equipments = len(summary.reports)
        summary.total_lanes = len(summary.all_readings)
        summary.total_failures = len(summary.failed_readings)
        return summary
