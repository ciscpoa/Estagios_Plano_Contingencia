# -*- coding: utf-8 -*-
"""
poaclima_scraper.py
===================
Scraping com Selenium (SEMPRE headless — nenhuma janela abre) do Poaclima:
https://prefeitura.poa.br/poaclima/

A página é um APP DE MAPA (Monitoramento Hidrometeorológico da Defesa
Civil): os níveis das estações fluviométricas e os alertas por região
NÃO estão no texto da página — aparecem em POPUPS ao clicar nos
marcadores, e o app pode estar dentro de um IFRAME.

Estratégia:
  1. Carrega a página e ENTRA no iframe com conteúdo (se houver).
  2. Liga a camada "Estações Fluviométricas" se o botão existir.
  3. CLICA em cada marcador do mapa e lê o popup:
       • popup com "Risco:"  → alerta regional (Defesa Civil)
       • popup com "N,NN m"  → medidor de nível (Gasômetro, Cais Mauá,
         Riacho Ipiranga/Dilúvio e demais estações)
  4. Fallback: se os valores estiverem no texto corrido, o parser
     ancorado em rótulos continua funcionando.

Também mantém o fallback do nível do Guaíba via nivelguaiba.com.
"""

from __future__ import annotations

import re
import time
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from coleta.webdriver_utils import criar_driver

_RE_NIVEL = re.compile(r"(\d{1,2})[.,](\d{1,2})\s*m\b", re.I)
_RE_CHUVA = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*mm", re.I)

# ── Popups de ALERTA regional (por subprefeitura/região) ─────────────────
_RE_REGIAO = re.compile(r"\((\d{1,2})\)\s*([A-Za-zÀ-úçÇ][A-Za-zÀ-úçÇ \-]{1,40})")
_RE_CAMPO = {
    "risco":     re.compile(r"Risco:\s*(.+)", re.I),
    "inicio":    re.compile(r"In[íi]cio:\s*([\d/]+\s*[\d:]*)", re.I),
    "fim":       re.compile(r"Fim:\s*([\d/]+\s*[\d:]*)", re.I),
    "tipo":      re.compile(r"Tipo:\s*(.+)", re.I),
    "descricao": re.compile(r"Descri[çc][ãa]o:\s*(.+)", re.I | re.S),
}

_SELETORES_MARCADOR = (".leaflet-marker-icon, .leaflet-interactive, "
                       "[class*='marker'], [class*='Marker'], "
                       "img[src*='marker'], img[src*='pin']")
_SELETORES_POPUP = (".leaflet-popup-content, [class*='popup'], [class*='Popup'], "
                    "[class*='modal'], [class*='Modal'], [class*='drawer'], "
                    "[class*='painel'], [class*='card'], [class*='Card']")
_SELETORES_FECHAR = ("[class*='close'], [class*='Close'], "
                     "[aria-label*='echar'], [aria-label*='lose'], "
                     ".leaflet-popup-close-button")


def _parse_popup_alerta(texto: str) -> dict | None:
    """Interpreta popup de alerta regional (Risco/Tipo/Início/Fim/Descrição)."""
    if "Risco:" not in texto:
        return None
    alerta: dict = {"regiao_num": None, "regiao_nome": None}
    m = _RE_REGIAO.search(texto)
    if m:
        alerta["regiao_num"] = int(m.group(1))
        alerta["regiao_nome"] = m.group(2).replace("Ver bairros", "").strip()
    for campo, regex in _RE_CAMPO.items():
        mm = regex.search(texto)
        valor = mm.group(1).strip() if mm else None
        if campo == "descricao" and valor:
            valor = " ".join(valor.split())[:400]
        alerta[campo] = valor
    return alerta if alerta.get("risco") else None


def _classificar_medidor(texto: str) -> str | None:
    """Identifica a qual medidor conhecido o popup pertence (pelos rótulos)."""
    t = texto.lower()
    for chave, rotulos in config.MEDIDORES_POACLIMA.items():
        if any(r in t for r in rotulos):
            return chave
    return None


def _extrair_niveis_medidores(corpo: str) -> dict:
    """
    Fallback textual: extrai os medidores quando os valores aparecem no
    texto corrido, com detecção de orientação (nome→valor vs valor→nome).
    """
    corpo_l = corpo.lower()
    achados = []
    for chave, rotulos in config.MEDIDORES_POACLIMA.items():
        for rotulo in rotulos:
            pos = corpo_l.find(rotulo)
            if pos != -1:
                achados.append((pos, pos + len(rotulo), chave))
                break
    achados.sort()
    vazio = {chave: None for chave in config.MEDIDORES_POACLIMA}
    if not achados:
        return vazio

    def _valor(trecho: str, ultimo: bool = False) -> float | None:
        ms = list(_RE_NIVEL.finditer(trecho))
        if not ms:
            return None
        m = ms[-1] if ultimo else ms[0]
        return float(f"{m.group(1)}.{m.group(2)}")

    depois, antes = dict(vazio), dict(vazio)
    for i, (pos, fim, chave) in enumerate(achados):
        lim = achados[i + 1][0] if i + 1 < len(achados) else min(len(corpo), fim + 200)
        depois[chave] = _valor(corpo[fim:lim])
        ini = achados[i - 1][1] if i > 0 else max(0, pos - 200)
        antes[chave] = _valor(corpo[ini:pos], ultimo=True)

    escolhido = depois if sum(v is not None for v in depois.values()) >= \
        sum(v is not None for v in antes.values()) else antes
    outro = antes if escolhido is depois else depois
    for chave in escolhido:
        if escolhido[chave] is None:
            escolhido[chave] = outro[chave]
    return escolhido


# ──────────────────────────────────────────────────────────────────────────
# NAVEGAÇÃO NO APP DE MAPA
# ──────────────────────────────────────────────────────────────────────────
def _corpo(driver) -> str:
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except Exception:
        return ""


def _entrar_no_conteudo(driver, espera_s: int = 20) -> str:
    """
    O app pode estar num IFRAME. Procura (por até `espera_s`) o contexto
    com mais texto e PERMANECE nele. Retorna o texto encontrado.
    """
    fim = time.time() + espera_s
    melhor_texto, melhor_frame = "", None
    while time.time() < fim:
        driver.switch_to.default_content()
        texto = _corpo(driver)
        if len(texto) > 200:
            return texto
        if len(texto) > len(melhor_texto):
            melhor_texto, melhor_frame = texto, None

        try:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
        except Exception:
            iframes = []
        for idx in range(len(iframes)):
            try:
                driver.switch_to.default_content()
                driver.switch_to.frame(idx)
                t = _corpo(driver)
                if len(t) > len(melhor_texto):
                    melhor_texto, melhor_frame = t, idx
                if len(t) > 200:
                    return t  # permanece dentro deste iframe
            except Exception:
                continue
        driver.switch_to.default_content()
        time.sleep(2)

    if melhor_frame is not None:
        try:
            driver.switch_to.frame(melhor_frame)
        except Exception:
            driver.switch_to.default_content()
    return melhor_texto


def _ligar_camada_fluviometrica(driver):
    """Clica no botão/atalho 'Estações Fluviométricas' se existir."""
    try:
        botoes = driver.find_elements(
            By.XPATH, "//*[contains(text(),'Fluviom') or contains(text(),'fluviom')]")
        for b in botoes[:3]:
            try:
                driver.execute_script("arguments[0].click();", b)
                time.sleep(1.0)
            except Exception:
                pass
    except Exception:
        pass


def _texto_popup(driver, baseline: str) -> str:
    """Texto do popup aberto: seletores conhecidos → fallback diff do body."""
    candidatos = []
    try:
        for el in driver.find_elements(By.CSS_SELECTOR, _SELETORES_POPUP):
            try:
                t = el.text.strip()
                if t and ("Risco:" in t or _RE_NIVEL.search(t)):
                    candidatos.append(t)
            except Exception:
                continue
    except Exception:
        pass
    if candidatos:
        return max(candidatos, key=len)

    # fallback: linhas novas no body em relação ao baseline
    atual = _corpo(driver)
    base_linhas = set(baseline.splitlines())
    novas = [l for l in atual.splitlines() if l.strip() and l not in base_linhas]
    return "\n".join(novas)


def _fechar_popup(driver):
    try:
        botoes = driver.find_elements(By.CSS_SELECTOR, _SELETORES_FECHAR)
        if botoes:
            driver.execute_script("arguments[0].click();", botoes[-1])
        else:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.4)
    except Exception:
        pass


def _explorar_marcadores(driver, baseline: str, limite: int = 60):
    """
    Clica em cada marcador do mapa e coleta:
      • níveis (medidores conhecidos + demais estações em `outros`)
      • alertas regionais da Defesa Civil
    """
    niveis = {chave: None for chave in config.MEDIDORES_POACLIMA}
    outros: dict[str, float] = {}
    alertas: list[dict] = []
    vistos: set[tuple] = set()

    try:
        marcadores = driver.find_elements(By.CSS_SELECTOR, _SELETORES_MARCADOR)
    except Exception:
        marcadores = []
    print(f"[Poaclima] {len(marcadores)} marcador(es) candidatos no mapa.")

    for el in marcadores[:limite]:
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});"
                "arguments[0].dispatchEvent(new MouseEvent('click',"
                "{bubbles:true, cancelable:true, view:window}));", el)
            time.sleep(1.0)
            texto = _texto_popup(driver, baseline)
            if not texto:
                continue

            alerta = _parse_popup_alerta(texto)
            if alerta:
                chave = (alerta.get("regiao_num"), alerta.get("tipo"), alerta.get("inicio"))
                if chave not in vistos:
                    vistos.add(chave)
                    alertas.append(alerta)
            else:
                m = _RE_NIVEL.search(texto)
                if m:
                    valor = float(f"{m.group(1)}.{m.group(2)}")
                    chave_med = _classificar_medidor(texto)
                    if chave_med and niveis.get(chave_med) is None:
                        niveis[chave_med] = valor
                    elif not chave_med:
                        nome = texto.splitlines()[0][:60] if texto.splitlines() else "estacao"
                        outros.setdefault(nome, valor)
            _fechar_popup(driver)
        except Exception:
            continue

    return niveis, outros, alertas


# ──────────────────────────────────────────────────────────────────────────
# FUNÇÕES PÚBLICAS
# ──────────────────────────────────────────────────────────────────────────
def coletar_poaclima() -> dict:
    """
    Retorna:
      {
        "alerta_vigente", "chuva_acumulada_mm",
        "niveis": {usina_gasometro_m, cais_maua_m, riacho_ipiranga_m},
        "outros_medidores": {nome: nivel_m},
        "alertas_regionais": [ {...}, ... ],
        "texto_bruto", "url_usada",
      }
    """
    resultado = {
        "alerta_vigente": None,
        "chuva_acumulada_mm": None,
        "niveis": {chave: None for chave in config.MEDIDORES_POACLIMA},
        "outros_medidores": {},
        "alertas_regionais": [],
        "texto_bruto": "",
        "url_usada": None,
    }
    try:
        driver = criar_driver()
    except Exception as exc:
        print(f"[Poaclima] Selenium indisponível (seguindo sem): {exc}")
        return resultado

    try:
        driver.get(config.URL_POACLIMA)
        WebDriverWait(driver, config.SELENIUM_TIMEOUT_S).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))

        corpo = _entrar_no_conteudo(driver, espera_s=20)
        resultado["url_usada"] = config.URL_POACLIMA
        resultado["texto_bruto"] = corpo[:2000]
        print(f"[Poaclima] Conteúdo carregado ({len(corpo)} chars de texto).")

        corpo_l = corpo.lower()
        for termo in ("alerta de risco extremo", "alerta de risco muito alto",
                      "alerta de risco alto", "aviso de atenção",
                      "alerta vermelho", "alerta laranja", "alerta amarelo"):
            if termo in corpo_l:
                resultado["alerta_vigente"] = termo.title()
                break
        m = _RE_CHUVA.search(corpo)
        if m:
            resultado["chuva_acumulada_mm"] = float(m.group(1).replace(",", "."))

        # fallback textual + exploração dos marcadores (fonte principal)
        resultado["niveis"] = _extrair_niveis_medidores(corpo)
        _ligar_camada_fluviometrica(driver)
        niveis_click, outros, alertas = _explorar_marcadores(driver, baseline=corpo)
        for chave, valor in niveis_click.items():
            if valor is not None:
                resultado["niveis"][chave] = valor
        resultado["outros_medidores"] = outros
        resultado["alertas_regionais"] = alertas
    except Exception as exc:
        print(f"[Poaclima] Falha no scraping: {exc}")
    finally:
        driver.quit()

    n = resultado["niveis"]
    print(f"[Poaclima] alerta={resultado['alerta_vigente']} "
          f"chuva={resultado['chuva_acumulada_mm']} mm | "
          f"Gasômetro={n['usina_gasometro_m']} · Cais Mauá={n['cais_maua_m']} · "
          f"Riacho Ipiranga={n['riacho_ipiranga_m']} | "
          f"{len(resultado['outros_medidores'])} outra(s) estação(ões) | "
          f"{len(resultado['alertas_regionais'])} alerta(s) regional(is)")
    return resultado


_RE_DIA = re.compile(r"(\d{1,2})[./](\d{1,2})")
_RE_MM = re.compile(r"(\d{1,3})\s*mm", re.I)
_RE_TEMP = re.compile(r"(-?\d{1,2})\s*°\s*C", re.I)  # o ° é obrigatório:
# sem ele, "28.07\nChuva" casava como "07 C" (temperatura fantasma)
_RE_UMID = re.compile(r"(\d{1,3})\s*%")
_RE_VENTO = re.compile(r"(\d{1,3})\s*km/h", re.I)


def _parse_previsao(texto: str) -> list[dict]:
    """
    Interpreta a tabela "Previsão do tempo" do Poaclima (dados da Catavento).
    Cada dia aparece como um bloco:
        Dom 26.07 | Pancadas de chuva isoladas | 15 mm |
        23 °C 13 °C | 98 % 84 % | 30 km/h | NO
    """
    ano = datetime.now().year
    dias: list[dict] = []
    for bloco in re.split(r"(?=(?:Dom|Seg|Ter|Qua|Qui|Sex|S[áa]b)\s*\d{1,2}[./])",
                          texto):
        m_dia = _RE_DIA.search(bloco or "")
        if not m_dia:
            continue
        chuva = _RE_MM.search(bloco)
        if not chuva:
            continue        # sem coluna de chuva → não é linha de previsão
        temps = [int(t) for t in _RE_TEMP.findall(bloco)[:2]]
        umid = [int(u) for u in _RE_UMID.findall(bloco)[:2]]
        vento = _RE_VENTO.search(bloco)

        # descrição = primeira linha textual sem números
        descricao = None
        for linha in (bloco.splitlines()):
            limpa = linha.strip()
            if (limpa and not _RE_DIA.search(limpa) and "mm" not in limpa
                    and "°" not in limpa and "%" not in limpa
                    and "km/h" not in limpa and len(limpa) > 3):
                descricao = limpa
                break
        try:
            data = datetime(ano, int(m_dia.group(2)), int(m_dia.group(1)))
        except ValueError:
            continue
        dias.append({
            "data": data,
            "descricao": descricao,
            "precipitacao_total_mm": float(chuva.group(1)),
            "temp_max_c": temps[0] if temps else None,
            "temp_min_c": temps[1] if len(temps) > 1 else None,
            "umidade_max_pct": umid[0] if umid else None,
            "umidade_min_pct": umid[1] if len(umid) > 1 else None,
            "vento_kmh": int(vento.group(1)) if vento else None,
        })
    # remove duplicatas mantendo a ordem
    vistos, unicos = set(), []
    for d in dias:
        if d["data"] not in vistos:
            vistos.add(d["data"])
            unicos.append(d)
    return unicos


def coletar_previsao_poaclima() -> dict:
    """
    Abre a aba "Previsão do tempo" do Poaclima e lê a tabela de previsão
    (fonte: Catavento Meteorologia — a mesma que a Defesa Civil de POA usa).

    Retorna {"dias": [...], "previsto_48h_mm": float|None, "fonte", "ok"}
    """
    vazio = {"dias": [], "previsto_48h_mm": None,
             "fonte": "Poaclima/Catavento", "ok": False}
    try:
        driver = criar_driver()
    except Exception as exc:
        print(f"[Poaclima-previsão] Selenium indisponível: {exc}")
        return vazio

    try:
        driver.get(config.URL_POACLIMA)
        WebDriverWait(driver, config.SELENIUM_TIMEOUT_S).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        _entrar_no_conteudo(driver, espera_s=20)

        # clica no botão "Previsão do tempo"
        clicou = False
        for xp in ("//*[contains(text(),'Previsão do tempo')]",
                   "//*[contains(text(),'Previsao do tempo')]"):
            for el in driver.find_elements(By.XPATH, xp)[:3]:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    clicou = True
                    break
                except Exception:
                    continue
            if clicou:
                break
        if not clicou:
            print("[Poaclima-previsão] botão 'Previsão do tempo' não encontrado.")
        time.sleep(2.5)

        texto = _corpo(driver)
        dias = _parse_previsao(texto)
        if not dias:
            print("[Poaclima-previsão] tabela não interpretada "
                  f"({len(texto)} chars lidos).")
            return vazio

        hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        proximos = [d for d in dias if d["data"] >= hoje][:2]
        previsto_48h = sum(d["precipitacao_total_mm"] for d in proximos) or 0.0

        print(f"[Poaclima-previsão] {len(dias)} dia(s) lidos | "
              f"próximas 48h: {previsto_48h:.0f} mm (Catavento)")
        return {"dias": dias, "previsto_48h_mm": previsto_48h,
                "fonte": "Poaclima/Catavento", "ok": True}
    except Exception as exc:
        print(f"[Poaclima-previsão] falha: {exc}")
        return vazio
    finally:
        driver.quit()


def coletar_nivel_guaiba_fallback() -> dict:
    """Fallback do nível do Guaíba via nivelguaiba.com (quando a ANA falhar)."""
    nivel = None
    try:
        driver = criar_driver()
    except Exception as exc:
        print(f"[NivelGuaiba] Selenium indisponível (seguindo sem): {exc}")
        return {"nivel_m": None, "fonte": "nivelguaiba.com"}
    try:
        driver.get(config.URL_NIVEL_GUAIBA_PMPA)
        WebDriverWait(driver, config.SELENIUM_TIMEOUT_S).until(
            EC.presence_of_element_located((By.TAG_NAME, "body")))
        m = _RE_NIVEL.search(_corpo(driver))
        if m:
            nivel = float(f"{m.group(1)}.{m.group(2)}")
    except Exception as exc:
        print(f"[NivelGuaiba] Falha no scraping: {exc}")
    finally:
        driver.quit()
    print(f"[NivelGuaiba] nível fallback = {nivel} m")
    return {"nivel_m": nivel, "fonte": "nivelguaiba.com"}
