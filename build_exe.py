"""
Script de Compilação Automatizada para gerar o Executável Standalone (.exe) do Windows.
Usa PyInstaller para empacotar o Python, Playwright e módulos em uma pasta portátil.
"""

import os
import subprocess
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def build_executables():
    print("=" * 70)
    print("[*] COMPILANDO EXECUTAVEL STANDALONE (.EXE) DO PROJETO COM PYINSTALLER")
    print("=" * 70)


    base_dir = os.path.dirname(__file__)

    # 1. Compilação do main.py -> ControleFluxoViario.exe
    main_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name", "ControleFluxoViario",
        "--collect-all", "playwright",
        "--add-data", f"{os.path.join(base_dir, 'src')};src",
        os.path.join(base_dir, "main.py")
    ]

    print("\n📦 1. Compilando ControleFluxoViario.exe...")
    ret_main = subprocess.run(main_cmd)
    if ret_main.returncode != 0:
        print("❌ Erro ao compilar ControleFluxoViario.exe")
        return False

    # 2. Compilação do login_assistido.py -> ResolverCaptcha.exe
    login_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--console",
        "--name", "ResolverCaptcha",
        "--collect-all", "playwright",
        "--add-data", f"{os.path.join(base_dir, 'src')};src",
        os.path.join(base_dir, "login_assistido.py")
    ]

    print("\n📦 2. Compilando ResolverCaptcha.exe...")
    ret_login = subprocess.run(login_cmd)
    if ret_login.returncode != 0:
        print("❌ Erro ao compilar ResolverCaptcha.exe")
        return False

    print("\n" + "=" * 70)
    print("🎉 COMPILAÇÃO CONCLUÍDA COM SUCESSO!")
    print("Os executáveis estão prontos na pasta 'dist/':")
    print("  • dist/ControleFluxoViario/ControleFluxoViario.exe")
    print("  • dist/ResolverCaptcha/ResolverCaptcha.exe")
    print("=" * 70)
    return True


if __name__ == "__main__":
    build_executables()
