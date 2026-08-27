"""
Script de Login Assistido com Resolução de Captcha.

Como funciona:
1. Abre o navegador real com janela visível na sua máquina.
2. Preenche seu usuário e senha automaticamente.
3. Você resolve o Captcha com o mouse e clica em 'Acessar/Entrar'.
4. O script detecta o login bem-sucedido e salva os cookies e tokens em 'session_state.json'.
5. O arquivo 'session_state.json' é usado tanto para execuções locais quanto para o GitHub Actions (via Secret).
"""

import json
import os
import sys
import time
from src.config import settings

# Garante suporte a UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_assisted_login():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ Playwright não instalado. Execute: pip install playwright && playwright install chromium")
        return

    session_file = os.path.join(os.path.dirname(__file__), "session_state.json")

    print("=" * 70)
    print("🔑 INICIANDO LOGIN ASSISTIDO (RESOLUÇÃO DE CAPTCHA)")
    print("=" * 70)
    print("1. O navegador será aberto na sua tela.")
    print("2. Usuário e senha serão preenchidos automaticamente (se configurados no .env).")
    print("3. Resolva o Captcha na tela com o mouse e clique no botão para entrar.")
    print("4. Assim que entrar no sistema, este script salvará sua sessão automaticamente!")
    print("=" * 70)

    with sync_playwright() as pw:
        # Abre o navegador com interface gráfica visível
        launch_kwargs = {
            "headless": False,
            "args": [
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ]
        }
        try:
            browser = pw.chromium.launch(channel="chrome", **launch_kwargs)
        except Exception:
            browser = pw.chromium.launch(**launch_kwargs)

        context = browser.new_context(
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        context.add_init_script("delete Object.getPrototypeOf(navigator).webdriver")
        page = context.new_page()

        print(f"\n🌐 Acessando página de login: {settings.SITE_LOGIN_URL}")
        page.goto(settings.SITE_LOGIN_URL, wait_until="networkidle")

        # Tenta preencher login e senha automaticamente para adiantar
        try:
            if settings.SITE_USERNAME:
                user_input = page.locator(settings.SELECTOR_USERNAME_INPUT).first
                if user_input.is_visible():
                    user_input.fill(settings.SITE_USERNAME)
                    print(f"✓ Usuário '{settings.SITE_USERNAME}' preenchido.")

            if settings.SITE_PASSWORD:
                pass_input = page.locator(settings.SELECTOR_PASSWORD_INPUT).first
                if pass_input.is_visible():
                    pass_input.fill(settings.SITE_PASSWORD)
                    print("✓ Senha preenchida.")
        except Exception as e:
            print(f"⚠️ Preenchimento automático: {e}")

        print("\n👉 AGUARDANDO VOCÊ RESOLVER O CAPTCHA E CLICAR EM ENTRAR NO NAVEGADOR...")
        print("(Tempo limite: 3 minutos)")

        # Aguarda a URL mudar para fora da tela de login (indica sucesso)
        max_wait = 180  # 3 minutos
        start = time.time()
        logged_in = False

        while time.time() - start < max_wait:
            current_url = page.url
            # Se saiu de auth/login, consideramos logado
            if "auth/login" not in current_url and "#/auth/login" not in current_url and current_url != settings.SITE_LOGIN_URL:
                # Aguarda 2 segundos para os cookies de autenticação serem gravados
                page.wait_for_timeout(2500)
                logged_in = True
                break
            time.sleep(1)

        if logged_in:
            # Salva o estado de sessão completo (cookies, localStorage, tokens)
            context.storage_state(path=session_file)
            print("\n" + "=" * 70)
            print("🎉 SUCESSO! LOGIN DETECTADO E SESSÃO SALVA!")
            print(f"📁 Arquivo salvo em: {session_file}")
            print("=" * 70)
            print("\n📋 COMO USAR NO GITHUB ACTIONS:")
            print("1. Abra o arquivo 'session_state.json' que foi gerado na pasta do projeto.")
            print("2. Copie todo o conteúdo do arquivo (Ctrl+A e Ctrl+C).")
            print("3. Acesse o GitHub: Settings -> Secrets and variables -> Actions -> New repository secret.")
            print("4. Crie uma secret chamada: SESSION_STATE_JSON e cole o conteúdo lá.")
            print("5. Pronto! O GitHub Actions usará essa sessão e não pedirá mais Captcha.")
            print("=" * 70)
        else:
            print("\n❌ Tempo limite excedido. O login não foi concluído.")

        browser.close()


if __name__ == "__main__":
    run_assisted_login()
