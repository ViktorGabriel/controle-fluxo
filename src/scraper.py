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
        """Encerra as instâncias do navegador de forma segura, evitando processos órfãos."""
        if self.page:
            try:
                self.page.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar página: {e}")
            finally:
                self.page = None

        if self.context:
            try:
                self.context.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar contexto: {e}")
            finally:
                self.context = None

        if self.browser:
            try:
                self.browser.close()
            except Exception as e:
                logger.debug(f"Aviso ao fechar navegador: {e}")
            finally:
                self.browser = None

        if self.playwright:
            try:
                self.playwright.stop()
            except Exception as e:
                logger.debug(f"Aviso ao parar playwright: {e}")
            finally:
                self.playwright = None

        logger.info("Recursos do navegador encerrados com sucesso.")

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

    def _ensure_filter_modal_open(self):
        """Garante que o modal 'Filtrar no mapa' está aberto e visível."""
        try:
            modal = self.page.locator("modal-filter-mapa, mat-dialog-container:has-text('Filtrar no mapa')")
            if modal.count() == 0 or not modal.first.is_visible():
                btn_filtro = self.page.locator(
                    "button:has-text('Filtrar'), [title*='Filtrar'], [aria-label*='Filtrar'], .btn-filtro, .btn-filter"
                ).first
                if btn_filtro.is_visible():
                    logger.info("Abrindo modal 'Filtrar no mapa'...")
                    btn_filtro.click()
                    try:
                        self.page.wait_for_selector(
                            "modal-filter-mapa, mat-dialog-container, input#mat-input-0, input[placeholder*='equipamento']",
                            state="visible",
                            timeout=2500
                        )
                    except Exception:
                        self.page.wait_for_timeout(300)
        except Exception as e:
            logger.warning(f"Erro ao abrir modal de filtro: {e}")

    def _fill_month_year(self):
        """Preenche o campo de Mês/Ano no modal apenas se necessário."""
        now = datetime.now(BRT)
        current_iso_month = now.strftime("%Y-%m")
        try:
            dt_input = self.page.locator("input#dtInicial, tvc-datetime input, input[type='month']").first
            if dt_input.is_visible():
                current_val = dt_input.input_value()
                if current_val != current_iso_month:
                    dt_input.fill(current_iso_month)
                    self.page.wait_for_timeout(100)
        except Exception as e:
            logger.warning(f"Aviso ao preencher data: {e}")

    def _discover_and_get_lanes(self, equipment_id: str) -> List[str]:
        """Digita o equipamento no input, aguarda o autocomplete, captura todas as opções de faixas e seleciona a primeira."""
        try:
            equip_input = self.page.locator(
                "input#mat-input-0, input[placeholder*='equipamento'], input[formcontrolname='equipamentoMapa']"
            ).first
            if not equip_input.is_visible():
                return [equipment_id]

            equip_input.click()
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Backspace")

            # Digita para disparar o autocomplete do Angular
            self.page.keyboard.type(equipment_id, delay=40)
            
            # Aguarda o painel do autocomplete abrir
            try:
                self.page.wait_for_selector(
                    ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option",
                    state="visible",
                    timeout=2000
                )
            except Exception:
                self.page.wait_for_timeout(300)

            # Coleta todas as opções correspondentes às faixas
            opts = self.page.query_selector_all(
                ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option"
            )
            matched_lanes = []
            for o in opts:
                txt = o.inner_text().strip()
                txt_clean = " ".join(txt.split())
                if equipment_id.lower() in txt_clean.lower():
                    matched_lanes.append(txt_clean)

            matched_lanes = list(dict.fromkeys(matched_lanes))

            # Se encontrou opções, clica na primeira opção para já deixar selecionada
            if matched_lanes:
                first_opt = self.page.locator(
                    ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option"
                ).filter(has_text=re.compile(rf"{re.escape(matched_lanes[0])}", re.IGNORECASE)).first
                if first_opt.count() > 0 and first_opt.is_visible():
                    first_opt.click()
                    self.page.wait_for_timeout(200)
                return matched_lanes

            # Se não abriu lista, tenta confirmar com Enter
            self.page.keyboard.press("ArrowDown")
            self.page.keyboard.press("Enter")
            self.page.wait_for_timeout(200)
            return [equipment_id]

        except Exception as e:
            logger.warning(f"Erro na descoberta de faixas para {equipment_id}: {e}")
            return [equipment_id]

    def _select_lane_in_input(self, base_radar: str, faixa_num: Optional[str] = None):
        """Digita o radar no autocomplete e seleciona a faixa desejada por texto ou posição."""
        try:
            equip_input = self.page.locator(
                "input#mat-input-0, input[placeholder*='equipamento'], input[formcontrolname='equipamentoMapa']"
            ).first
            if equip_input.is_visible():
                equip_input.click()
                self.page.keyboard.press("Control+A")
                self.page.keyboard.press("Backspace")

                self.page.keyboard.type(base_radar, delay=35)
                try:
                    self.page.wait_for_selector(
                        ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option",
                        state="visible",
                        timeout=2000
                    )
                except Exception:
                    self.page.wait_for_timeout(250)

                opts = self.page.query_selector_all(
                    ".mat-mdc-autocomplete-panel mat-option, [role='option'], .mat-option"
                )
                
                # Filtra opções que pertencem a este radar
                matching_opts = [o for o in opts if base_radar.lower() in o.inner_text().lower()]
                if not matching_opts:
                    matching_opts = opts

                selected_opt = None
                
                # 1. Tenta encontrar opção cujo texto contenha especificamente a faixa (ex: "4" ou "- 4" ou "Faixa 4")
                if faixa_num and matching_opts:
                    for o in matching_opts:
                        txt = o.inner_text().strip()
                        if re.search(rf"(?:-|\bFaixa\b|\b)\s*{re.escape(faixa_num)}\b", txt, re.IGNORECASE):
                            selected_opt = o
                            break

                # 2. Se não encontrou por texto mas faixa_num é numérico, seleciona por índice (ex: faixa 1 -> índice 0, faixa 4 -> índice 3)
                if not selected_opt and faixa_num and matching_opts:
                    try:
                        num = int(faixa_num)
                        if 1 <= num <= len(matching_opts):
                            selected_opt = matching_opts[num - 1]
                        else:
                            # Caso as faixas comecem em números como 4 e 5 (ex: SBR286), seleciona pela ordem
                            selected_opt = matching_opts[0]
                    except ValueError:
                        pass

                # 3. Fallback: primeira opção correspondente
                if not selected_opt and matching_opts:
                    selected_opt = matching_opts[0]

                if selected_opt:
                    selected_opt.click()
                    self.page.wait_for_timeout(200)
                else:
                    self.page.keyboard.press("ArrowDown")
                    self.page.keyboard.press("Enter")
                    self.page.wait_for_timeout(200)
        except Exception as e:
            logger.warning(f"Erro ao selecionar radar {base_radar} (Faixa: {faixa_num}): {e}")

    def _click_search_and_wait(self):
        """Clica no botão de pesquisar e aguarda reativamente a renderização dos dados."""
        try:
            btn_busca = self.page.locator(
                "tvc-button[icon='search'] button, button.primary.radius:has(mat-icon:has-text('search'))"
            ).first
            if btn_busca.count() > 0 and btn_busca.is_visible():
                btn_busca.click(force=True)
            else:
                modal_buttons = self.page.query_selector_all("button")
                for b in reversed(modal_buttons):
                    if b.is_visible():
                        b.click(force=True)
                        break

            logger.info("⏳ Aguardando renderização do mapa e carregamento completo...")
            try:
                self.page.wait_for_selector("tvc-placeholder-mapa-chart", state="detached", timeout=30000)
            except Exception:
                pass

            # Aguarda reativamente o DOM estar pronto com os dados do gráfico
            try:
                self.page.wait_for_function("""() => {
                    const placeholder = document.querySelector('tvc-placeholder-mapa-chart');
                    if (placeholder && placeholder.offsetParent !== null) return false;
                    const cards = document.querySelectorAll('.main.flex.flex-col:has(card-header-mapa), .main.flex.flex-col');
                    if (cards.length === 0) return false;
                    for (let c of cards) {
                        const svg = c.querySelector('apx-chart svg, .apexcharts-svg, svg');
                        if (svg && svg.querySelectorAll('rect').length > 0) return true;
                        if (window.ng && window.ng.getComponent) {
                            const chartEl = c.querySelector('chart-mapa-unificado-minute') || c;
                            const comp = window.ng.getComponent(chartEl);
                            if (comp && comp.chartOptions && comp.chartOptions.series && comp.chartOptions.series.length > 0) return true;
                        }
                    }
                    return false;
                }""", timeout=4000)
            except Exception:
                self.page.wait_for_timeout(800)
        except Exception as e:
            logger.warning(f"Erro ao clicar na busca: {e}")

    def _scroll_full_page(self):
        """Dispara eventos de scroll e redimensionamento em lote para renderização rápida dos cards."""
        try:
            self.page.evaluate("""() => {
                document.querySelectorAll('.overflow-y-auto, [cdkScrollable], mat-sidenav-content, .main-content').forEach(el => {
                    el.scrollTop = 50;
                    el.dispatchEvent(new Event('scroll'));
                });
                window.dispatchEvent(new Event('resize'));
            }""")
            self.page.wait_for_timeout(100)
        except Exception:
            pass

    def _extract_cards(self, report, timestamp, base_radar, formatted_lane, faixa_num, current_day):
        """Extrai o card da faixa correspondente renderizada na tela."""
        cards = self.page.query_selector_all(".main.flex.flex-col:has(card-header-mapa), .main.flex.flex-col")
        if cards:
            logger.info(f"📊 Detectados {len(cards)} cards na tela.")
            target_card = None
            for c in cards:
                header = c.query_selector("card-header-mapa")
                txt = header.inner_text().strip() if header else c.inner_text().strip()
                if faixa_num and f"- {faixa_num}" in txt:
                    target_card = c
                    break
                elif base_radar in txt:
                    target_card = c

            if not target_card and cards:
                target_card = cards[0]

            if target_card:
                try:
                    target_card.scroll_into_view_if_needed(timeout=1000)
                except Exception:
                    pass

                for _ in range(6):
                    has_rendered = target_card.evaluate("""el => {
                        if (window.ng && window.ng.getComponent) {
                            const chartEl = el.querySelector('chart-mapa-unificado-minute') || el;
                            const comp = window.ng.getComponent(chartEl);
                            if (comp && comp.chartOptions && comp.chartOptions.series && comp.chartOptions.series.length > 0) return true;
                        }
                        const svg = el.querySelector('apx-chart svg, .apexcharts-svg, svg');
                        if (svg && svg.querySelectorAll('rect').length > 0) return true;
                        return false;
                    }""")
                    if has_rendered:
                        break
                    self.page.wait_for_timeout(150)

                eval_result = target_card.evaluate("""(el, todayDay) => {
                    const chartEl = el.querySelector('chart-mapa-unificado-minute') || el;
                    if (window.ng && window.ng.getComponent) {
                        try {
                            const comp = window.ng.getComponent(chartEl);
                            if (comp && comp.chartOptions && comp.chartOptions.series) {
                                const series = comp.chartOptions.series;
                                let intervalsToday = [];
                                for (let s of series) {
                                    if (s.data && s.data.length >= todayDay) {
                                        const pt = s.data[todayDay - 1];
                                        if (pt !== null && pt !== undefined) {
                                            let val = 0;
                                            let isRed = false;
                                            if (typeof pt === 'number') {
                                                val = pt;
                                                isRed = (val === 0);
                                            } else if (typeof pt === 'object') {
                                                val = Number(pt.y !== undefined ? pt.y : (Array.isArray(pt) ? pt[1] : 0));
                                                isRed = (val === 0 || (pt.fillColor && String(pt.fillColor).toLowerCase().includes('red')));
                                            }
                                            intervalsToday.push({
                                                time: s.name || '',
                                                val: val,
                                                isRed: isRed
                                            });
                                        }
                                    }
                                }
                                if (intervalsToday.length > 0) {
                                    const last2 = intervalsToday.slice(-2);
                                    const bothRed = last2.length === 2 && last2.every(r => r.isRed || r.val === 0);
                                    const lastOneRed = last2.length >= 1 && (last2[last2.length - 1].isRed || last2[last2.length - 1].val === 0);
                                    
                                    let status = 'OK';
                                    let reason = 'Operação Normal';
                                    if (bothRed) {
                                        status = 'FALHA';
                                        reason = '🚨 OFFLINE: Penúltimo e último períodos consecutivos em vermelho / sem fluxo';
                                    } else if (lastOneRed) {
                                        status = 'ALERTA';
                                        reason = '⚠️ ALERTA: Último período em vermelho (penúltimo operou normalmente)';
                                    }
                                    const lastVal = last2.length > 0 ? (last2[last2.length - 1].val > 0 ? last2[last2.length - 1].val : 0.0) : 1.0;
                                    return { status, reason, value: (status === 'OK' && lastVal === 0 ? 1.0 : lastVal) };
                                }
                            }
                        } catch (e) {}
                    }

                    const svg = el.querySelector('apx-chart svg') || el.querySelector('.apexcharts-svg') || el.querySelector('svg');
                    if (!svg) {
                        return { status: 'OK', reason: 'Operação Normal', value: 1.0 };
                    }

                    const rawRects = Array.from(svg.querySelectorAll(
                        '.apexcharts-heatmap-rect, g.apexcharts-heatmap rect, g.apexcharts-series rect, apx-chart svg rect, svg rect'
                    ));
                    
                    const rects = rawRects.filter(r => {
                        const w = parseFloat(r.getAttribute('width') || (r.getBoundingClientRect && r.getBoundingClientRect().width) || 0);
                        const h = parseFloat(r.getAttribute('height') || (r.getBoundingClientRect && r.getBoundingClientRect().height) || 0);
                        return w > 1 && w < 600 && h > 1 && h < 150;
                    }).map(r => {
                        const xAttr = r.getAttribute('x');
                        const yAttr = r.getAttribute('y');
                        const bbox = r.getBoundingClientRect ? r.getBoundingClientRect() : { left: 0, top: 0 };
                        return {
                            x: xAttr !== null ? parseFloat(xAttr) : bbox.left,
                            y: yAttr !== null ? parseFloat(yAttr) : bbox.top,
                            fill: (r.getAttribute('fill') || r.style.fill || r.style.backgroundColor || '').toLowerCase(),
                            val: parseFloat(r.getAttribute('val') || r.getAttribute('data-val') || r.getAttribute('data:val') || 0)
                        };
                    });

                    if (rects.length === 0) {
                        return { status: 'OK', reason: 'Operação Normal', value: 1.0 };
                    }

                    rects.sort((a, b) => a.x - b.x);
                    const columns = [];
                    for (let r of rects) {
                        let col = columns.find(c => Math.abs(c.x - r.x) <= 8);
                        if (!col) {
                            col = { x: r.x, cells: [] };
                            columns.push(col);
                        }
                        col.cells.push(r);
                    }
                    columns.sort((a, b) => a.x - b.x);

                    let todayCol = (columns.length >= todayDay) ? columns[todayDay - 1] : columns[columns.length - 1];
                    const todayCells = todayCol ? todayCol.cells.sort((a, b) => a.y - b.y) : [];

                    const activeToday = todayCells.filter(r => {
                        return r.fill && !r.fill.includes('#f3f4f6') && !r.fill.includes('#e5e7eb') && !r.fill.includes('#ffffff') && !r.fill.includes('transparent') && !r.fill.includes('none');
                    });

                    const isRed = (fill, val) => {
                        return (fill.includes('#ef4444') || fill.includes('#fee2e2') || fill.includes('#fca5a5') || fill.includes('rgb(254') || fill.includes('rgb(239') || fill.includes('rgb(220') || fill.includes('red')) || (val === 0);
                    };

                    if (activeToday.length > 0) {
                        const last2 = activeToday.slice(-2);
                        const bothRed = last2.length === 2 && last2.every(r => isRed(r.fill, r.val));
                        const lastOneRed = last2.length >= 1 && isRed(last2[last2.length - 1].fill, last2[last2.length - 1].val);

                        let status = 'OK';
                        let reason = 'Operação Normal';
                        if (bothRed) {
                            status = 'FALHA';
                            reason = '🚨 OFFLINE: Penúltimo e último períodos consecutivos em vermelho / sem fluxo';
                        } else if (lastOneRed) {
                            status = 'ALERTA';
                            reason = '⚠️ ALERTA: Último período em vermelho (penúltimo operou normalmente)';
                        }

                        const lastVal = last2.length > 0 ? (last2[last2.length - 1].val > 0 ? last2[last2.length - 1].val : 0.0) : 1.0;
                        return { status, reason, value: (status === 'OK' && lastVal === 0 ? 1.0 : lastVal) };
                    }

                    return { status, reason: 'Operação Normal', value: 1.0 };
                }""", current_day)

                status_str = eval_result.get("status", "OK")
                status_enum = StatusEnum.FALHA if status_str == "FALHA" else (StatusEnum.ALERTA if status_str == "ALERTA" else StatusEnum.OK)
                reason_str = eval_result.get("reason", "Operação Normal")
                is_red = (status_enum in (StatusEnum.FALHA, StatusEnum.ALERTA))
                
                reading = LaneReading(
                    timestamp=timestamp,
                    equipment_id=base_radar,
                    lane_number=formatted_lane,
                    flow_value=float(eval_result.get("value", 1.0)),
                    raw_value=str(eval_result.get("value", "1.0")),
                    is_red_highlighted=is_red,
                    status=status_enum,
                    failure_reason=reason_str if status_enum != StatusEnum.OK else "Operação Normal"
                )
                report.readings.append(reading)
                logger.info(f"   ✓ Faixa extraída: {formatted_lane} -> {status_enum.value} ({reading.failure_reason})")

    def scrape_equipment_lanes(self, target_lane: str, timestamp: str) -> EquipmentReport:
        """Aplica o filtro para uma faixa ou equipamento e extrai a leitura com precisão."""
        if not self.page:
            return EquipmentReport(equipment_id=target_lane, error_message="Página não inicializada")

        # Decompõe o target (ex: 'SBR402-1' -> base='SBR402', faixa='1', formatted='SBR402 - 1')
        if "-" in target_lane:
            parts = target_lane.split("-")
            base_radar = parts[0].strip()
            faixa_num = parts[1].strip()
            formatted_lane = f"{base_radar} - {faixa_num}"
        else:
            base_radar = target_lane.strip()
            faixa_num = None
            formatted_lane = base_radar

        logger.info(f"🔍 Consultando radar: {base_radar} (Faixa: {formatted_lane})")
        report = EquipmentReport(equipment_id=base_radar)
        now_brt = datetime.now(BRT)
        current_day = now_brt.day

        try:
            # 1. Garante que o modal 'Filtrar no mapa' está aberto
            self._ensure_filter_modal_open()

            # 2. Preenche o mês/ano
            self._fill_month_year()

            # 3. Digita o radar e seleciona a faixa desejada no autocomplete
            self._select_lane_in_input(base_radar, faixa_num)

            # 4. Clica em Pesquisar e aguarda estabilização
            self._click_search_and_wait()

            # 5. Rolagem completa da página
            self._scroll_full_page()

            # 6. Extrai o card da faixa
            self._extract_cards(report, timestamp, base_radar, formatted_lane, faixa_num, current_day)

            if report.readings:
                report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
                return report

            # 3. Fallback: Itera sobre as linhas de tabela padrão caso seja exibida em formato tabular
            rows = self.page.query_selector_all(settings.SELECTOR_LANE_ROWS)
            if not rows:
                rows = self.page.query_selector_all("table tr, tbody tr, .mat-row, tr")

            if not rows:
                logger.warning(f"Nenhuma linha encontrada na grade para o radar {base_radar} (Faixa: {formatted_lane})")
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

                # Fallback: atribui a leitura consolidada ao equipamento geral
                lane_names = [formatted_lane]
                for l_name in lane_names:
                    reading = FlowAnalyzer.evaluate_consecutive_readings(
                        timestamp=timestamp,
                        equipment_id=base_radar,
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

                    lane_name = cells[0].inner_text().strip() if len(cells) > 0 else f"{formatted_lane} ({idx})"
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
                            equipment_id=base_radar,
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
                            equipment_id=base_radar,
                            lane_number=lane_name,
                            raw_value=raw_val,
                            is_red_highlighted=is_red
                        )

                    report.readings.append(reading)

            report.has_failures = any(r.status == StatusEnum.FALHA for r in report.readings)
            return report

        except PlaywrightTimeoutError:
            logger.error(f"Timeout ao carregar dados do equipamento {base_radar} (Faixa: {formatted_lane})")
            report.error_message = "Timeout de carregamento"
            return report
        except Exception as e:
            logger.error(f"Erro ao extrair equipamento {base_radar} (Faixa: {formatted_lane}): {e}")
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
                summary.success = False
                summary.error_message = "Falha na autenticação / Login não concluído"
                return summary

            # Navega até a página de fluxos se for diferente da URL pós-login
            if settings.SITE_FLOWS_URL and settings.SITE_FLOWS_URL != self.page.url:
                logger.info(f"Navegando para página de mapa/fluxos: {settings.SITE_FLOWS_URL}")
                self.page.goto(settings.SITE_FLOWS_URL, wait_until="domcontentloaded")

            # Aguarda reativamente o botão de filtro e módulos SPA estarem prontos
            wait_sec = settings.INITIAL_PAGE_WAIT_SECONDS
            logger.info("⏳ Aguardando estabilização inicial do mapa e módulos do portal...")
            try:
                self.page.wait_for_selector(
                    "button:has-text('Filtrar'), .btn-filtro, [title*='Filtrar'], .leaflet-container, canvas, tvc-button",
                    state="visible",
                    timeout=max(wait_sec * 1000, 5000)
                )
                self.page.wait_for_timeout(500)
            except Exception:
                self.page.wait_for_timeout(1500)

            equipments = self.get_equipment_list()
            if not equipments:
                logger.warning("Nenhum equipamento retornado pelo portal ou configurado no .env.")
                summary.success = False
                summary.error_message = "Nenhum equipamento retornado pelo portal ou configurado no .env"
                return summary

            for equip in equipments:
                rep = self.scrape_equipment_lanes(equip, timestamp)
                summary.reports.append(rep)
                if self.page:
                    self.page.wait_for_timeout(400)

            summary.total_equipments = len(summary.reports)
            summary.total_lanes = len(summary.all_readings)
            summary.total_failures = len(summary.failed_readings)
            summary.success = True
            return summary

        except Exception as e:
            logger.error(f"Erro inesperado durante a execução do scan: {e}")
            summary.success = False
            summary.error_message = str(e)
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
