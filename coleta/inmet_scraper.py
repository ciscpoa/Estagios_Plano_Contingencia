# -*- coding: utf-8 -*-
"""
inmet_scraper.py
================
Scraping do INMET com Selenium (headless):

1. `alertas2.inmet.gov.br` — avisos meteorológicos vigentes para o RS /
   Região Metropolitana de Porto Alegre (Amarelo / Laranja / Vermelho).
2. Tenta ainda a API pública de avisos (apiprevmet3) como caminho rápido,
   caindo para o Selenium se a API falhar.

Saída padronizada:
    {
      "alertas": [ {"severidade": "Laranja", "descricao": "...", "inicio":..., "fim":...} ],
      "max_severidade": "Laranja" | "Amarelo" | "Vermelho" | None,
      "fonte": "api" | "selenium",
    }
"""

from __future__ import annotations

import re

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from coleta.webdriver_utils import criar_driver

_ORDEM_SEVERIDADE = {"Amarelo": 1, "Laranja": 2, "Vermelho": 3}
_UF_ALVO = "RS"
_TERMOS_POA = ("porto alegre", "metropolitana", "rio grande do sul", "litoral norte")


# ──────────────────────────────────────────────────────────────────────────
# Caminho 1 — API de avisos do INMET (rápida, sem browser)
# ──────────────────────────────────────────────────────────────────────────
def _tentar_api() -> dict | None:
    # A API do INMET retorna 403 sem um User-Agent de navegador
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept": "application/json",
        "Referer": "https://alertas2.inmet.gov.br/",
    }
    from coleta.rede import forcar_ipv4
    forcar_ipv4()
    avisos = None
    for tentativa in (1, 2):
        try:
            r = requests.get("https://apiprevmet3.inmet.gov.br/avisos/ativos",
                             headers=headers, timeout=(8, 15))
            r.raise_for_status()
            avisos = r.json()
            break
        except Exception as exc:
            print(f"[INMET] API tentativa {tentativa}/2 falhou ({exc})")
            if tentativa == 2:
                print("[INMET] API indisponível; usando Selenium.")
                return None
            import time as _t
            _t.sleep(3)

    encontrados = []
    for av in avisos if isinstance(avisos, list) else []:
        estados = str(av.get("estados", "")).lower()
        municipios = str(av.get("municipios", "")).lower()
        if ("rio grande do sul" in estados or "rs" in estados.split(",")
                or any(t in municipios for t in _TERMOS_POA)):
            sev = str(av.get("severidade", "")).strip().capitalize()
            sev = {"Perigo potencial": "Amarelo", "Perigo": "Laranja",
                   "Grande perigo": "Vermelho"}.get(sev, sev)
            encontrados.append({
                "severidade": sev if sev in _ORDEM_SEVERIDADE else "Amarelo",
                "descricao": av.get("descricao") or av.get("aviso_cor") or "",
                "inicio": av.get("data_inicio"),
                "fim": av.get("data_fim"),
            })
    return {"alertas": encontrados, "fonte": "api", "consultado": True}


# ──────────────────────────────────────────────────────────────────────────
# Caminho 2 — Selenium no site de alertas
# ──────────────────────────────────────────────────────────────────────────
def _scrape_selenium() -> dict:
    encontrados = []
    try:
        driver = criar_driver()
    except Exception as exc:
        print(f"[INMET] Selenium indisponível (seguindo sem): {exc}")
        return {"alertas": [], "fonte": "selenium", "consultado": False}
    try:
        import time as _t
        for tentativa in (1, 2):
            try:
                driver.get(config.URL_INMET_ALERTAS)
                WebDriverWait(driver, config.SELENIUM_TIMEOUT_S).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body")))
                break
            except Exception as exc:
                print(f"[INMET] Selenium tentativa {tentativa}/2 falhou "
                      f"({str(exc)[:80]})")
                if tentativa == 2:
                    raise
                _t.sleep(4)
        # os avisos aparecem como cards/linhas; capturamos texto e cor
        candidatos = driver.find_elements(
            By.CSS_SELECTOR,
            "table tr, .card, [class*='aviso'], [class*='alert'], [class*='warning']",
        )
        for el in candidatos:
            texto = el.text.strip()
            if not texto or len(texto) < 15:
                continue
            texto_l = texto.lower()
            if not any(t in texto_l for t in _TERMOS_POA):
                continue
            sev = None
            if "grande perigo" in texto_l or "vermelho" in texto_l:
                sev = "Vermelho"
            elif re.search(r"\bperigo\b", texto_l) or "laranja" in texto_l:
                sev = "Laranja"
            elif "perigo potencial" in texto_l or "amarelo" in texto_l:
                sev = "Amarelo"
            if sev:
                encontrados.append({
                    "severidade": sev,
                    "descricao": texto[:300],
                    "inicio": None,
                    "fim": None,
                })
    except Exception as exc:
        print(f"[INMET] Falha no scraping Selenium: {exc}")
    finally:
        driver.quit()
    return {"alertas": encontrados, "fonte": "selenium", "consultado": True}


# ──────────────────────────────────────────────────────────────────────────
# Função pública
# ──────────────────────────────────────────────────────────────────────────
def coletar_alertas_inmet() -> dict:
    """Coleta avisos vigentes do INMET para POA/RS (API → fallback Selenium)."""
    resultado = _tentar_api()
    if resultado is None or not isinstance(resultado.get("alertas"), list):
        resultado = _scrape_selenium()

    alertas = resultado["alertas"]
    max_sev = None
    if alertas:
        max_sev = max(alertas, key=lambda a: _ORDEM_SEVERIDADE.get(a["severidade"], 0))["severidade"]

    resultado["max_severidade"] = max_sev
    print(f"[INMET] {len(alertas)} aviso(s) p/ POA-RS | máx: {max_sev} | fonte: {resultado['fonte']}")
    return resultado


if __name__ == "__main__":
    print(coletar_alertas_inmet())
