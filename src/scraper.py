import logging
import os
import re
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any
from src.config import settings
from src.models import EquipmentReport, LaneReading, ScanSummary, StatusEnum
from src.analyzer import FlowAnalyzer

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)

# Fuso horário oficial de Brasília (UTC-3)
BRT = timezone(timedelta(hours=-3))


class PortalScraper:
    """Gerencia a automação no navegador com Playwright para extração dos dados de fluxo."""

    def __init__(self):
        self.playwright = None
        self.browser: Optional[Any] = None
        self.context: Optional[Any] = None
        self.page: Optional[Any] = None
        self.session_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session_state.json")

    def _get_current_timestamp(self) -> str:
        """Retorna a data e hora atual formatada no fuso horário de Brasília (UTC-3)."""
        return datetime.now(BRT).strftime("%d/%m/%Y %H:%M:%S")

    def start_browser(self):
        """Inicializa o navegador Playwright com perfil anti-detecção e reutiliza sessão salva."""
        self.playwright = sync_playwright().start()
        
        # Tenta lançar usando o Chrome nativo ou Chromium com flags stealth
        launch_kwargs = {
            "headless": settings.HEADLESS,
            "args": [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized"
            ]
        }
        try:
            self.browser = self.playwright.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            self.browser = self.playwright.chromium.launch(**launch_kwargs)

        context_kwargs = {
            "no_viewport": True,
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        if os.path.exists(self.session_file):
            logger.info("🔑 Sessão prévia encontrada (session_state.json). Reutilizando autenticação.")
            context_kwargs["storage_state"] = self.session_file

        self.context = self.browser.new_context(**context_kwargs)
        # Remove a flag navigator.webdriver
        self.context.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
        
        self.page = self.context.new_page()
        self.page.set_default_timeout(settings.BROWSER_TIMEOUT_MS)
        logger.info(f"Navegador Playwright iniciado (Headless={settings.HEADLESS}).")

    def close_browser(self):
        """Encerra as instâncias do navegador de forma segura."""
        try:
            if self.page:
                self.page.close()
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            logger.info("Navegador encerrado.")
        except Exception as e:
            logger.warning(f"Erro ao fechar navegador: {e}")

    def is_authenticated(self) -> bool:
        """Verifica se a página atual está fora da tela de login."""
        if not self.page:
            return False
        current_url = self.page.url
        return "auth/login" not in current_url and "#/auth/login" not in current_url

    def login(self) -> bool:
        """Efetua login no portal ou reutiliza sessão ativa."""
        if not self.page:
            raise RuntimeError("Navegador não inicializado.")

        # 1. Tenta acessar diretamente a URL de fluxos se já tiver sessão salva
        if os.path.exists(self.session_file):
            logger.info(f"Verificando se sessão salva ainda é válida em: {settings.SITE_FLOWS_URL}")
            try:
                self.page.goto(settings.SITE_FLOWS_URL, wait_until="domcontentloaded")
                self.page.wait_for_timeout(3000)
                if self.is_authenticated():
                    logger.info("✅ Sessão salva ainda é válida! Login reutilizado com sucesso.")
                    return True
                else:
                    logger.info("Sessão salva expirou. Realizando novo login...")
            except Exception:
                pass

        logger.info(f"Acessando tela de login: {settings.SITE_LOGIN_URL}")
        try:
            self.page.goto(settings.SITE_LOGIN_URL, wait_until="domcontentloaded")
            self.page.wait_for_timeout(2000)  # Aguarda carregamento do Angular/SPA

            # Preenchimento de usuário e senha
            logger.info("Preenchendo credenciais de acesso...")
            self.page.wait_for_selector(settings.SELECTOR_USERNAME_INPUT, state="visible", timeout=settings.BROWSER_TIMEOUT_MS)
            
            # Limpa e digita para disparar os eventos reativos do Angular
            self.page.click(settings.SELECTOR_USERNAME_INPUT)
            self.page.fill(settings.SELECTOR_USERNAME_INPUT, settings.SITE_USERNAME)
            self.page.click(settings.SELECTOR_PASSWORD_INPUT)
            self.page.fill(settings.SELECTOR_PASSWORD_INPUT, settings.SITE_PASSWORD)
            self.page.wait_for_timeout(500)

            # Clique no botão de login ("Acessar")
            logger.info("Clicando no botão de login ('Acessar')...")
            self.page.click(settings.SELECTOR_LOGIN_BUTTON)

            # Aguarda a autenticação e o redirecionamento (espera até 90 segundos caso haja desafio de imagens reCAPTCHA)
            logger.info("👉 Aguardando confirmação de login... Se houver desafio de imagens (CAPTCHA) no navegador, resolva-o.")
            login_success = False
            for sec in range(1, 91):
                self.page.wait_for_timeout(1000)
                if self.is_authenticated():
                    login_success = True
                    break
                if sec % 15 == 0:
                    logger.info(f"⏳ Aguardando autenticação ({sec}s/90s)... Resolva o captcha na janela se solicitado.")

            if login_success:
                logger.info("🎉 Login efetuado com sucesso!")
                # Salva a sessão para não precisar fazer login nas próximas execuções
                try:
                    self.context.storage_state(path=self.session_file)
                    logger.info("💾 Sessão salva em 'session_state.json' com sucesso.")
                except Exception as e:
                    logger.warning(f"Não foi possível salvar session_state.json: {e}")
                return True
            else:
                logger.error(
                    "❌ O login não foi concluído dentro de 90s. "
                    "Se o CAPTCHA de imagens estava visível, resolva as fotos no navegador aberto para concluir."
                )
                try:
                    self.page.screenshot(path="debug_login.png")
                    logger.info("📸 Screenshot de diagnóstico salvo em 'debug_login.png'.")
                except Exception:
                    pass
                return False

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout durante o processo de login: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado durante o login: {e}")
            return False

    def get_equipment_list(self) -> List[str]:
        """Obtém a lista de equipamentos configurados manualmente ou do menu/select."""
        # 1. Se foi configurada lista manual no .env / config
        configured = settings.get_configured_equipments()
        if configured:
            logger.info(f"Usando lista de {len(configured)} equipamentos configurados no .env: {configured}")
            return configured

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
            logger.warning(
                f"Não foi possível obter lista automática do select: {e}. "
                f"Verifique SELECTOR_EQUIPMENT_FILTER ou configure EQUIPMENT_LIST no seu .env."
            )
            return []

    def open_filter_and_search(self, equipment_id: str) -> bool:
        """Abre o modal 'Filtrar no mapa', preenche Mês/Ano e Equipamento, e clica no botão de busca."""
        if not self.page:
            return False

        now = datetime.now()
        mes_ano_num = now.strftime("%m%Y")  # ex: 082026 para inputs com máscara

        try:
            # 1. Garante que o modal 'Filtrar no mapa' está aberto para a busca atual
            modal = self.page.locator("*:has-text('Filtrar no mapa')")
            if modal.count() == 0 or not modal.first.is_visible():
                btn_filtro = self.page.locator(
                    "button:has-text('Filtrar'), [title*='Filtrar'], [aria-label*='Filtrar'], .btn-filtro, .btn-filter"
                ).first
                if btn_filtro.is_visible():
                    logger.info("Abrindo modal 'Filtrar no mapa'...")
                    btn_filtro.click()
                    self.page.wait_for_timeout(1500)

            # 2. PRIMEIRO: Preenchimento nativo do campo Mês/Ano (ISO YYYY-MM)
            current_iso_month = now.strftime("%Y-%m")  # ex: '2026-08'
            logger.info(f"📅 [Passo 1/2] Preenchendo Mês/Ano: {current_iso_month}...")
            try:
                self.page.fill("input#dtInicial, tvc-datetime input, input[type='month']", current_iso_month)
                self.page.wait_for_timeout(800)
                val = self.page.locator("input#dtInicial, tvc-datetime input").input_value()
                logger.info(f"✅ Mês/Ano preenchido e validado: '{val}'")
            except Exception as e:
                logger.warning(f"Aviso ao preencher data: {e}")

            # 3. SEGUNDO: Preenchimento do Equipamento
            logger.info(f"🚗 [Passo 2/2] Preenchendo equipamento: {equipment_id}...")
            equip_input = self.page.locator(
                "input#mat-input-0, input[placeholder*='equipamento'], input[formcontrolname='equipamentoMapa'], input"
            ).first
            if equip_input.is_visible():
                equip_input.click()
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")
                self.page.wait_for_timeout(200)

                # Digita tecla por tecla para disparar os eventos do autocomplete Angular
                self.page.keyboard.type(equipment_id, delay=120)
                self.page.wait_for_timeout(1500)

                # Localiza a opção correspondente ao equipamento digitado no autocomplete
                matched_opt = self.page.locator(
                    ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option"
                ).filter(has_text=re.compile(rf"{equipment_id}", re.IGNORECASE)).first

                if matched_opt.count() > 0 and matched_opt.is_visible():
                    logger.info(f"Clicando na opção do autocomplete para {equipment_id}...")
                    matched_opt.click()
                    self.page.wait_for_timeout(800)
                else:
                    logger.info(f"Opção exata não encontrada no dropdown, confirmando com Enter...")
                    self.page.keyboard.press("ArrowDown")
                    self.page.wait_for_timeout(200)
                    self.page.keyboard.press("Enter")
                    self.page.wait_for_timeout(800)

            # 4. Clique no botão de Buscar (círculo preto com ícone de lupa)
            self.page.wait_for_timeout(1000)
            logger.info("🔎 Clicando no botão de busca (lupa)...")
            
            btn_busca = self.page.locator("tvc-button[icon='search'] button, button.primary.radius:has(mat-icon:has-text('search'))").first
            if btn_busca.count() > 0 and btn_busca.is_visible():
                btn_busca.click(force=True)
            else:
                modal_buttons = self.page.query_selector_all("button")
                for b in reversed(modal_buttons):
                    if b.is_visible():
                        b.click(force=True)
                        break

            # 5. Aguarda o término do carregamento da grade e estabilização completa
            logger.info("⏳ Aguardando renderização do mapa e dos fluxos do equipamento...")
            try:
                self.page.wait_for_selector("tvc-placeholder-mapa-chart", state="detached", timeout=45000)
            except Exception:
                pass

            logger.info("⏳ Aguardando 8s para estabilização completa dos gráficos e faixas...")
            for s in range(1, 9):
                self.page.wait_for_timeout(1000)
                if s % 4 == 0:
                    logger.info(f"   Estabilizando mapa ({s}/8s)...")

            return True
        except Exception as e:
            logger.warning(f"Erro ao aplicar filtro para {equipment_id}: {e}")
            try:
                self.page.screenshot(path="debug_filter_error.png")
            except Exception:
                pass
            return False

    def scrape_equipment_lanes(self, equipment_id: str, timestamp: str) -> EquipmentReport:
        """Aplica o filtro para um equipamento base e extrai os dados de todas as faixas retornadas."""
        if not self.page:
            return EquipmentReport(equipment_id=equipment_id, error_message="Página não inicializada")

        logger.info(f"🔍 Consultando equipamento: {equipment_id}")
        report = EquipmentReport(equipment_id=equipment_id)

        try:
            # 1. Executa a busca no modal de filtro
            self.open_filter_and_search(equipment_id)

            # 2. Localiza cards de faixas na tela (layout mapa unificado)
            cards = self.page.query_selector_all(".main.flex.flex-col:has(card-header-mapa), .main.flex.flex-col")
            if cards:
                logger.info(f"📊 Detectados {len(cards)} cards de faixas para o equipamento {equipment_id}")
                for idx, c in enumerate(cards, start=1):
                    header = c.query_selector("card-header-mapa")
                    txt = header.inner_text().strip() if header else c.inner_text().strip()
                    
                    # Extrai o nome da faixa (ex: GBR005 - 1)
                    match = re.search(r"Equipamento:\s*([^\n\r]+)", txt)
                    lane_name = match.group(1).strip() if match else f"{equipment_id} - {idx}"
                    
                    # Analisa a área do gráfico, isolando da legenda do cabeçalho
                    chart_area = c.query_selector("chart-mapa-unificado-minute, apx-chart")
                    has_red = False
                    if chart_area:
                        chart_txt = chart_area.inner_text().lower()
                        if "não há dados" in chart_txt or "offline" in chart_txt or "erro ao carregar" in chart_txt:
                            has_red = True
                        else:
                            # Busca apenas retângulos ou caminhos dentro da grade gráfica
                            chart_elements = chart_area.query_selector_all("rect.apexcharts-heatmap-rect, rect, path")
                            for el in chart_elements:
                                cls_attr = el.get_attribute("class") or ""
                                style_attr = el.get_attribute("style") or ""
                                fill_attr = el.get_attribute("fill") or ""
                                # Ignora elementos de fundo transparente/branco
                                if fill_attr in ("", "none", "#ffffff", "#fff", "transparent"):
                                    continue
                                if FlowAnalyzer.is_red_style(cls_attr, f"{style_attr} fill:{fill_attr}"):
                                    has_red = True
                                    break
                    
                    reading = FlowAnalyzer.evaluate_reading(
                        timestamp=timestamp,
                        equipment_id=equipment_id,
                        lane_number=lane_name,
                        raw_value="0" if has_red else "1",
                        is_red_highlighted=has_red
                    )
                    report.readings.append(reading)

                report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
                return report

            # 3. Fallback: Itera sobre as linhas de tabela padrão caso seja exibida em formato tabular
            rows = self.page.query_selector_all(settings.SELECTOR_LANE_ROWS)
            if not rows:
                rows = self.page.query_selector_all("table tr, tbody tr, .mat-row, tr")

            if not rows:
                logger.warning(f"Nenhuma linha encontrada na grade para o equipamento {equipment_id}")
                report.error_message = "Tabela vazia ou não carregada"
                return report

            # Verifica se é uma grade horária vertical (30 min por linha) ou horizontal (faixas por linha)
            first_row_text = rows[0].inner_text().strip()
            is_time_grid = any(h in first_row_text for h in ["00:00", "00:30", "01:00", "01:30", "02:00"])

            if is_time_grid:
                # Na grade horária, cada linha é um horário (00:00 -> 23:30) e colunas são os dias
                # Coleta as células da última coluna ativa (dia atual)
                col_cells = []
                for r in rows:
                    cells = r.query_selector_all("td, th, .mat-cell")
                    if len(cells) > 1:
                        # Pega a última célula com conteúdo/cor preenchida
                        last_active = None
                        for c in reversed(cells[1:]):
                            txt = c.inner_text().strip()
                            cls_attr = c.get_attribute("class") or ""
                            style_attr = c.get_attribute("style") or ""
                            if txt != "" or FlowAnalyzer.is_red_style(cls_attr, style_attr):
                                last_active = c
                                break
                        if last_active:
                            raw_val = last_active.inner_text().strip()
                            is_red = FlowAnalyzer.is_red_style(
                                last_active.get_attribute("class") or "",
                                last_active.get_attribute("style") or ""
                            )
                            col_cells.append({"value": raw_val, "is_red": is_red})

                # Se detectou faixas nos cabeçalhos (ex: SPK352 - 1)
                lane_names = detected_lanes if detected_lanes else [f"{equipment_id} (Geral)"]
                for l_name in lane_names:
                    reading = FlowAnalyzer.evaluate_consecutive_readings(
                        timestamp=timestamp,
                        equipment_id=equipment_id,
                        lane_number=l_name,
                        readings_history=col_cells[-5:] if len(col_cells) >= 2 else col_cells
                    )
                    report.readings.append(reading)
            else:
                # Modo padrão linha por faixa
                for idx, row in enumerate(rows, start=1):
                    cells = row.query_selector_all("td, th, .mat-cell")
                    if not cells:
                        continue

                    lane_name = cells[0].inner_text().strip() if len(cells) > 0 else f"Faixa {idx}"
                    row_class = row.get_attribute("class") or ""

                    if len(cells) > 2:
                        history = []
                        for cell in cells[1:]:
                            raw_val = cell.inner_text().strip()
                            cell_class = cell.get_attribute("class") or ""
                            cell_style = cell.get_attribute("style") or ""
                            is_red = FlowAnalyzer.is_red_style(f"{row_class} {cell_class}", cell_style)
                            history.append({"value": raw_val, "is_red": is_red})

                        reading = FlowAnalyzer.evaluate_consecutive_readings(
                            timestamp=timestamp,
                            equipment_id=equipment_id,
                            lane_number=lane_name,
                            readings_history=history
                        )
                    else:
                        value_cell = cells[1] if len(cells) > 1 else cells[0]
                        raw_val = value_cell.inner_text().strip()
                        cell_class = value_cell.get_attribute("class") or ""
                        cell_style = value_cell.get_attribute("style") or ""
                        is_red = FlowAnalyzer.is_red_style(f"{row_class} {cell_class}", cell_style)

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
                logger.info(f"Navegando para página de mapa/fluxos: {settings.SITE_FLOWS_URL}")
                self.page.goto(settings.SITE_FLOWS_URL, wait_until="domcontentloaded")

            # Aguarda a estabilização e carregamento completo do mapa e módulos SPA
            wait_sec = settings.INITIAL_PAGE_WAIT_SECONDS
            if wait_sec > 0:
                logger.info(f"⏳ Aguardando {wait_sec}s para o carregamento e estabilização completa do mapa/portal...")
                for s in range(1, wait_sec + 1):
                    self.page.wait_for_timeout(1000)
                    if s % 10 == 0 or s == wait_sec:
                        logger.info(f"   Carregando página do mapa ({s}/{wait_sec}s)...")

            equipments = self.get_equipment_list()
            if not equipments:
                logger.warning("Nenhum equipamento retornado pelo portal ou configurado no .env.")
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
        """Gera dados simulados com histórico consecutivo de períodos para teste."""
        timestamp = self._get_current_timestamp()
        summary = ScanSummary(execution_time=timestamp)

        # Simulações de equipamentos com leituras consecutivas (Antepenúltimo, Penúltimo, Último)
        mock_equipments = [
            (
                "RADAR-AV-BRASIL-KM12",
                [
                    ("Faixa 1", [{"value": "1350", "is_red": False}, {"value": "1420", "is_red": False}, {"value": "1380", "is_red": False}]),
                    ("Faixa 2", [{"value": "1100", "is_red": False}, {"value": "1250", "is_red": False}, {"value": "1190", "is_red": False}])
                ]
            ),
            (
                "RADAR-AV-PAULISTA-N200",
                [
                    # Penúltimo e Último Vermelhos -> FALHA / OFFLINE
                    ("Faixa 1", [{"value": "1200", "is_red": False}, {"value": "0", "is_red": True}, {"value": "", "is_red": True}]),
                    ("Faixa 2", [{"value": "900", "is_red": False}, {"value": "950", "is_red": False}, {"value": "920", "is_red": False}])
                ]
            ),
            (
                "RADAR-ROD-ANCHIETA-KM18",
                [
                    # Apenas o último vermelho -> ALERTA (não offline total)
                    ("Faixa 1", [{"value": "1100", "is_red": False}, {"value": "1050", "is_red": False}, {"value": "0", "is_red": True}]),
                    ("Faixa 2", [{"value": "1000", "is_red": False}, {"value": "1020", "is_red": False}, {"value": "980", "is_red": False}])
                ]
            )
        ]

        for eq_id, lanes in mock_equipments:
            report = EquipmentReport(equipment_id=eq_id)
            for l_name, hist in lanes:
                reading = FlowAnalyzer.evaluate_consecutive_readings(
                    timestamp=timestamp,
                    equipment_id=eq_id,
                    lane_number=l_name,
                    readings_history=hist
                )
                report.readings.append(reading)
            report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
            summary.reports.append(report)

        summary.total_equipments = len(summary.reports)
        summary.total_lanes = len(summary.all_readings)
        summary.total_failures = len(summary.failed_readings)
        return summary
