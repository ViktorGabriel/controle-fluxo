# 🛠️ Recomendações de Skills para o Projeto `Controle de Fluxo Viário`

Este documento lista as **Skills** mais recomendadas dos ecossistemas [rmyndharis/antigravity-skills](https://github.com/rmyndharis/antigravity-skills) e [sickn33/agentic-awesome-skills](https://github.com/sickn33/agentic-awesome-skills) para auditar, debugar e levar este projeto de automação a **100% de estabilidade e produção**.

---

## 📊 Mapeamento: Onde Estão os Pontos Críticos / Possíveis Bugs do Projeto?

1. **Scraper com Playwright (`src/scraper.py`):**
   * *Pontos de Falha:* Seletores dinâmicos no portal real, timeouts em conexões lentas, filtros SPA (dropdowns customizados), popups/iframes e detecção headless.
2. **Tratamento de Exceções & Depuração (`main.py` & `src/`):**
   * *Pontos de Falha:* Diagnosticar quedas no GitHub Actions sem interface gráfica, ausência de captura de screenshots/vídeos em caso de erro.
3. **Integração com Google Sheets (`src/sheets_service.py`):**
   * *Pontos de Falha:* Limites de requisições por minuto da API (Rate Limit 429), reautenticação de token expirado.
4. **Pipeline de CI/CD (`.github/workflows/daily_monitor.yml`):**
   * *Pontos de Falha:* Falhas transitórias no runner do GitHub, tempo de instalação de dependências e upload de artefatos de debug.

---

## 📦 Top 5 Skills Recomendadas para Instalação

### 1. 🌐 `playwright-skill` / `browser-automation`
* **Origem:** `sickn33/agentic-awesome-skills`
* **Foco no Projeto:** Automação do Portal e Resiliência de Scraping.
* **Por que instalar:**
  * Fornece padrões avançados de seletores CSS/XPath resilientes a mudanças no layout do portal.
  * Ensina o agente a interceptar requisições de rede (`page.wait_for_response` ou `page.route`) para ler diretamente o JSON do radar, eliminando a dependência do DOM visual quando possível.
  * Configura salvamento automático de traces e prints em caso de falha.

---

### 2. 🔍 `debugging-toolkit-smart-debug` / `error-diagnostics-smart-debug`
* **Origem:** `rmyndharis/antigravity-skills` & `sickn33/agentic-awesome-skills`
* **Foco no Projeto:** Resolução Rápida de Bugs e Análise de Causa-Raiz.
* **Por que instalar:**
  * Metodologia estruturada para isolar por que uma leitura falhou (se foi erro de rede, mudança de classe CSS no portal ou formato inesperado de número).
  * Evita correções por tentativa e erro, gerando diagnósticos com base em logs de erro e stacktraces.

---

### 3. 🐍 `python-pro` & `python-testing-patterns`
* **Origem:** `rmyndharis/antigravity-skills`
* **Foco no Projeto:** Qualidade de Código Python, Async e Testes Robustos.
* **Por que instalar:**
  * Padrões de código limpo em Python 3.11+, tipagem estática e arquitetura orientada a objetos.
  * Melhora a suíte de testes com mocks completos para a API do Google Sheets e para o Playwright (testes sem precisar abrir o portal real).
  * Gerenciamento correto de ciclo de vida de recursos (fechamento de navegadores, contexts e sessions sem vazamento de memória).

---

### 4. 🚀 `github-actions-templates` / `cicd-automation-workflow-automate`
* **Origem:** `sickn33/agentic-awesome-skills`
* **Foco no Projeto:** Otimização e Monitoramento do GitHub Actions.
* **Por que instalar:**
  * Adiciona retentativas automáticas (*retry on failure*) no workflow do GitHub Actions caso o portal tenha oscilação pontual.
  * Configura upload automático de artefatos (ex: print da tela do portal no momento do erro) para download direto na aba *Actions*.
  * Otimiza o cache do `pip` e dos binários do Chromium, reduzindo o tempo de build pela metade.

---

### 5. 🛡️ `code-reviewer` / `clean-code`
* **Origem:** `sickn33/agentic-awesome-skills` & `rmyndharis/antigravity-skills`
* **Foco no Projeto:** Auditoria Preventiva e Segurança.
* **Por que instalar:**
  * Executa uma varredura completa no projeto procurando por *edge cases* não tratados (ex: radar que retorna texto em vez de número, tabela sem linhas, timeout de login).
  * Garante que nenhuma chave ou segredo escape para arquivos de log.

---

## 💻 Como Instalar as Skills

### Via CLI / npx:
```bash
# Repositório sickn33/agentic-awesome-skills
npx agentic-awesome-skills install playwright-skill
npx agentic-awesome-skills install debugging-toolkit-smart-debug
npx agentic-awesome-skills install github-actions-templates

# Repositório rmyndharis/antigravity-skills
npx @rmyndharis/antigravity-skills install python-pro
npx @rmyndharis/antigravity-skills install error-diagnostics-smart-debug
```

### Via Antigravity CLI (agy):
```bash
agy plugin install https://github.com/rmyndharis/antigravity-skills
```

---

## 🎯 Ordem de Ação Recomendada

1. **Passo 1:** Instalar `playwright-skill` e `debugging-toolkit-smart-debug` para mapear os seletores exatos do portal da empresa e debugar a navegação.
2. **Passo 2:** Utilizar `python-pro` para criar testes de integração simulando respostas do portal e do Google Sheets.
3. **Passo 3:** Ajustar o workflow do GitHub Actions com `github-actions-templates` para gravar relatórios de execução e prints em caso de falha.
