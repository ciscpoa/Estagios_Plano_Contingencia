# -*- coding: utf-8 -*-
"""
webdriver_utils.py
==================
Fábrica de WebDriver do Selenium, adaptável ao ambiente:

* VSCode/local  → usa webdriver-manager para baixar o chromedriver correto.
* Google Colab  → usa o chromium/chromedriver instalados via apt
                  (ver célula de setup no notebook).

Sempre em modo headless por padrão (config.SELENIUM_HEADLESS).
"""

import shutil
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

import config


# ──────────────────────────────────────────────────────────────────────────
# Chrome for Testing: download automático (independe de apt/snap)
# ──────────────────────────────────────────────────────────────────────────
def _chrome_for_testing() -> tuple[str, str]:
    """
    Baixa o Chrome for Testing + chromedriver oficiais (linux64) direto do
    Google e retorna (caminho_chrome, caminho_chromedriver). É o fallback
    DEFINITIVO no Colab: não depende de apt (que falha com o snap stub).
    Fica em cache, então o download (~170 MB) acontece uma única vez.
    """
    import json as _json
    import stat
    import urllib.request
    import zipfile

    cache = Path("/content/cft") if config.IN_COLAB else config.BASE_DIR / ".cft"
    chrome_bin = cache / "chrome-linux64" / "chrome"
    driver_bin = cache / "chromedriver-linux64" / "chromedriver"
    if chrome_bin.exists() and driver_bin.exists():
        return str(chrome_bin), str(driver_bin)

    cache.mkdir(parents=True, exist_ok=True)
    meta_url = ("https://googlechromelabs.github.io/chrome-for-testing/"
                "last-known-good-versions-with-downloads.json")
    with urllib.request.urlopen(meta_url, timeout=60) as f:
        meta = _json.load(f)
    downloads = meta["channels"]["Stable"]["downloads"]

    def _url(tipo: str) -> str:
        return next(d["url"] for d in downloads[tipo] if d["platform"] == "linux64")

    for tipo in ("chrome", "chromedriver"):
        zpath = cache / f"{tipo}.zip"
        print(f"[Selenium] Baixando {tipo} (Chrome for Testing, 1ª vez apenas)...")
        urllib.request.urlretrieve(_url(tipo), zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(cache)
        zpath.unlink()

    for binario in (chrome_bin, driver_bin):
        binario.chmod(binario.stat().st_mode | stat.S_IEXEC)
    print(f"[Selenium] Chrome for Testing pronto em {cache}")
    return str(chrome_bin), str(driver_bin)


def criar_driver(headless: bool | None = None) -> webdriver.Chrome:
    """Retorna um Chrome WebDriver pronto para uso em qualquer ambiente."""
    if headless is None:
        headless = config.SELENIUM_HEADLESS

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--lang=pt-BR")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )

    if config.IN_COLAB:
        # No Colab moderno (Ubuntu 22+), o 'chromium-browser' do apt pode ser
        # um stub do snap. A célula de setup tenta: google-chrome (.deb) e,
        # como fallback, a receita chromium-chromedriver (StackOverflow).
        chrome = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
        chromium = shutil.which("chromium-browser") or shutil.which("chromium")
        binario = chrome or chromium
        if binario:
            opts.binary_location = binario

        chromedriver_sistema = (shutil.which("chromedriver")
                                or "/usr/lib/chromium-browser/chromedriver")

        # Ordem das tentativas:
        #  • com google-chrome → webdriver-manager 1º (driver na versão certa)
        #  • só com chromium   → chromedriver do sistema 1º (par casado da
        #    receita do StackOverflow), webdriver-manager depois
        def _via_wdm():
            from webdriver_manager.chrome import ChromeDriverManager
            return webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), options=opts)

        def _via_sistema():
            return webdriver.Chrome(
                service=Service(executable_path=chromedriver_sistema), options=opts)

        tentativas = [_via_wdm, _via_sistema] if chrome else [_via_sistema, _via_wdm]
        erros = []
        driver = None
        for tentar in tentativas:
            try:
                driver = tentar()
                break
            except Exception as exc:
                erros.append(str(exc)[:150])
        if driver is None:
            raise RuntimeError(
                "Não foi possível iniciar o Chrome/Chromium no Colab. Rode a "
                "célula de setup do Selenium (instala google-chrome ou "
                f"chromium-chromedriver). Erros: {' | '.join(erros)}")
    else:
        # Local: webdriver-manager resolve a versão do driver automaticamente
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)

    driver.set_page_load_timeout(config.SELENIUM_TIMEOUT_S + 10)
    return driver
