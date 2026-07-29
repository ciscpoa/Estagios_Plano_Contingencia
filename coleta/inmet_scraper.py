# -*- coding: utf-8 -*-
"""
inmet_scraper.py
================
Avisos meteorológicos do INMET para Porto Alegre.

Caminho 1 (rápido): API pública `apiprevmet3.inmet.gov.br/avisos/ativos`.
Caminho 2 (reserva): Selenium em `alertas2.inmet.gov.br`.

POR QUE ESTE ARQUIVO FOI REESCRITO
----------------------------------
O painel mostrava "nenhum aviso vigente" enquanto a Defesa Civil de POA
tinha as 17 regiões em "Tempestade – Chuvas Intensas". A causa era o
formato da resposta da API: ela NÃO devolve uma lista, e sim um envelope
(`{"hoje": [...], "futuro": [...]}`). O código antigo fazia

    for av in avisos if isinstance(avisos, list) else []

ou seja, descartava tudo em silêncio — a coleta "dava certo" com zero
avisos, que é o pior tipo de falha: parece dado, mas é ausência de dado.

Além disso o recorte geográfico era frágil: procurava "rio grande do sul"
num campo de texto. Agora o recorte é feito em três níveis, do mais forte
para o mais fraco:

  1. código IBGE de Porto Alegre (4314902) na lista de municípios;
  2. nome da mesorregião do INMET ("Metropolitana de Porto Alegre") ou
     do município com a UF ("Porto Alegre - RS");
  3. teste geométrico: o ponto de POA dentro do polígono do aviso.

Saída padronizada:
    {
      "alertas": [{"severidade","descricao","inicio","fim","tipo","criterio"}],
      "max_severidade": "Amarelo" | "Laranja" | "Vermelho" | None,
      "fonte": "api" | "selenium",
      "consultado": bool,
    }
"""

from __future__ import annotations

import json
import re

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from coleta.webdriver_utils import criar_driver

_ORDEM_SEVERIDADE = {"Amarelo": 1, "Laranja": 2, "Vermelho": 3}

# Coordenadas do centro de Porto Alegre (usadas no teste ponto-em-polígono)
_POA_LAT, _POA_LON = -30.0346, -51.2177
_IBGE_POA = "4314902"

# Termos que identificam POA com segurança. NÃO usar "porto alegre" solto:
# existem Porto Alegre do Norte (MT), do Piauí (PI) e do Tocantins (TO).
_TERMOS_POA = (
    _IBGE_POA,
    "metropolitana de porto alegre",
    "porto alegre - rs",
    "porto alegre-rs",
    "porto alegre/rs",
    "porto alegre (rs)",
)

# INMET publica a severidade com três nomes diferentes conforme o campo:
# o rótulo em português, a cor, e o grau CAP em inglês. Todos caem aqui.
_MAPA_SEVERIDADE = {
    "perigo potencial": "Amarelo", "perigo": "Laranja", "grande perigo": "Vermelho",
    "amarelo": "Amarelo", "laranja": "Laranja", "vermelho": "Vermelho",
    "minor": "Amarelo", "moderate": "Amarelo",
    "severe": "Laranja", "extreme": "Vermelho",
}

_URLS_API = (
    "https://apiprevmet3.inmet.gov.br/avisos/ativos",
    "https://apiprevmet3.inmet.gov.br/avisos",
)

_CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://avisos.inmet.gov.br/",
}


_CAMPOS_INICIO = ("data_inicio", "dt_inicio", "data_hora_inicio", "inicio",
                  "onset", "effective", "start", "data_inicial")
_CAMPOS_FIM = ("data_fim", "dt_fim", "data_hora_fim", "fim",
               "expires", "end", "data_final")
# O INMET separa DATA e HORA em campos distintos: data_inicio traz
# '2026-07-31T00:00:00.000Z' (só o calendário, o 'Z' é resíduo de
# serialização) e hora_inicio traz '00:00'. Ler só o primeiro fazia início e
# fim saírem idênticos no painel — um aviso que dura o dia inteiro aparecia
# como um instante.
_CAMPOS_HORA = {"inicio": ("hora_inicio", "hr_inicio"),
                "fim": ("hora_fim", "hr_fim")}


def _quando(av: dict, campos: tuple, ponta: str = "inicio") -> tuple[str, object]:
    """Devolve (texto legível, datetime) juntando a data e a hora do aviso."""
    import datetime as _dt
    formatos = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
    quando = None
    for campo in campos:
        bruto = av.get(campo)
        if bruto in (None, "", "null"):
            continue
        txt = str(bruto).strip()
        for f in formatos:
            try:
                # Sem conversão de fuso: o 'Z' vem de um toISOString() sobre
                # uma data de calendário, não de um instante UTC. Converter
                # jogaria um aviso que começa 00:00 para 21:00 do dia anterior.
                quando = _dt.datetime.strptime(txt, f)
                break
            except ValueError:
                continue
        if quando is not None:
            break
    if quando is None:
        return "", None

    for campo_hora in _CAMPOS_HORA.get(ponta, ()):
        h = str(av.get(campo_hora) or "").strip()
        m = re.match(r"^(\d{1,2})[:h](\d{2})", h)
        if m:
            quando = quando.replace(hour=int(m.group(1)), minute=int(m.group(2)))
            break

    return quando.strftime("%Y-%m-%d %H:%M"), quando


def _vigente_hoje(inicio, fim) -> bool:
    """
    True se a janela do aviso encosta no dia de hoje.

    O endpoint /ativos devolve também o que ainda vai começar. Um aviso para
    depois de amanhã não descreve a situação operacional de agora e não pode
    puxar o estágio da cidade — então ele sai da caixa e sai da severidade
    máxima. Quando a data não é legível, o aviso FICA: sumir com um aviso
    real por causa de um formato de data é o erro mais caro dos dois.
    """
    import datetime as _dt
    if inicio is None and fim is None:
        return True
    hoje = _dt.date.today()
    abre = _dt.datetime.combine(hoje, _dt.time.min)
    fecha = _dt.datetime.combine(hoje, _dt.time.max)
    if inicio is not None and inicio > fecha:
        return False
    if fim is not None and fim < abre:
        return False
    return True


# ──────────────────────────────────────────────────────────────────────────
# Normalização da resposta
# ──────────────────────────────────────────────────────────────────────────
def _achatar_avisos(obj) -> list[dict]:
    """
    Devolve TODOS os dicionários que parecem um aviso, em qualquer nível.

    Escrito assim de propósito: a API já mudou de `lista` para
    `{"hoje": [...], "futuro": [...]}` uma vez, e vai mudar de novo. Em vez
    de assumir uma forma, procuramos a assinatura de um aviso.
    """
    marcas = ("descricao", "severidade", "aviso_cor", "id_aviso",
              "data_inicio", "descricao_aviso")
    achados, pilha, visto = [], [obj], 0
    while pilha and visto < 20000:
        item = pilha.pop()
        visto += 1
        if isinstance(item, dict):
            if any(k in item for k in marcas):
                achados.append(item)
            else:
                pilha.extend(item.values())
        elif isinstance(item, (list, tuple)):
            pilha.extend(item)
    return achados


def _severidade(av: dict) -> str:
    """Traduz qualquer variante de severidade para Amarelo/Laranja/Vermelho."""
    for campo in ("aviso_cor", "severidade", "severity", "grau", "nivel"):
        bruto = str(av.get(campo) or "").strip().lower()
        if not bruto:
            continue
        if bruto in _MAPA_SEVERIDADE:
            return _MAPA_SEVERIDADE[bruto]
        # "Severidade Grau: Moderate", "Perigo Potencial", etc.
        for chave, cor in _MAPA_SEVERIDADE.items():
            if chave in bruto:
                return cor
    return "Amarelo"


def _pontos_do_poligono(bruto) -> list[tuple[float, float]]:
    """
    Extrai (lat, lon) de um polígono, aceitando string CAP ou lista aninhada.

    A ordem dos pares varia entre versões da API. Resolvemos pela faixa de
    valores: no RS a latitude fica entre -34 e -27 e a longitude entre -58
    e -49 — não há sobreposição, então dá para decidir sem adivinhar.
    """
    numeros = []
    if isinstance(bruto, str):
        numeros = [float(n) for n in re.findall(r"-?\d+\.\d+", bruto)]
    elif isinstance(bruto, (list, tuple)):
        pilha = [bruto]
        while pilha:
            it = pilha.pop(0)
            if isinstance(it, (list, tuple)):
                pilha[0:0] = list(it)
            elif isinstance(it, (int, float)):
                numeros.append(float(it))
    if len(numeros) < 6:
        return []
    pares = list(zip(numeros[0::2], numeros[1::2]))
    primeiros = [p[0] for p in pares]
    # se o primeiro valor está na faixa de longitude, o par é (lon, lat)
    if sum(1 for v in primeiros if v < -40) > len(primeiros) * 0.6:
        pares = [(b, a) for a, b in pares]
    return pares


def _ponto_no_poligono(lat: float, lon: float,
                       pares: list[tuple[float, float]]) -> bool:
    """Ray casting clássico. Sem shapely: o projeto roda em runner enxuto."""
    dentro, n = False, len(pares)
    if n < 3:
        return False
    for i in range(n):
        y1, x1 = pares[i]
        y2, x2 = pares[(i + 1) % n]
        if (y1 > lat) != (y2 > lat):
            corte = x1 + (lat - y1) * (x2 - x1) / ((y2 - y1) or 1e-12)
            if lon < corte:
                dentro = not dentro
    return dentro


def _abrange_poa(av: dict) -> str | None:
    """Devolve o critério que ligou o aviso a POA, ou None se não abrange."""
    texto = json.dumps(av, ensure_ascii=False, default=str).lower()
    if _IBGE_POA in texto:
        return "município (código IBGE 4314902)"
    for termo in _TERMOS_POA[1:]:
        if termo in texto:
            return "área do aviso"
    for campo in ("poligono", "poligonos", "geometry", "area_poligono", "polygon"):
        pares = _pontos_do_poligono(av.get(campo))
        if pares and _ponto_no_poligono(_POA_LAT, _POA_LON, pares):
            return "polígono do aviso contém Porto Alegre"
    return None


def _texto_util(valor) -> str:
    """
    Devolve o valor se ele for TEXTO EM PROSA; caso contrário, string vazia.

    A versão anterior pegava "o maior texto do aviso" e caiu direto numa
    armadilha: o aviso carrega a miniatura do mapa em base64, que é de longe
    a maior string do objeto — o painel exibiu `data:image/png;base64,...`.
    A lição é que tamanho não é sinal de conteúdo. Aqui a checagem é pelo
    FORMATO da prosa:

      * nada de data URI nem de campo com 'base64';
      * precisa de espaços — texto corrido tem muitos;
      * nenhuma "palavra" pode passar de 30 caracteres (base64, hashes,
        polígonos e WKT quebram exatamente aqui, português quase nunca);
      * maioria dos caracteres tem de ser letra ou espaço, o que descarta
        listas de coordenadas e de códigos IBGE.
    """
    if not isinstance(valor, str):
        return ""
    v = " ".join(valor.split()).strip()
    if not (30 <= len(v) <= 800):
        return ""
    baixo = v.lower()
    if baixo.startswith(("data:", "http://", "https://", "<svg", "<?xml")):
        return ""
    if "base64" in baixo:
        return ""
    if v.count(" ") < 4:
        return ""
    if max((len(p) for p in v.split(" ")), default=0) > 30:
        return ""
    letras = sum(1 for c in v if c.isalpha() or c == " ")
    if letras / len(v) < 0.7:
        return ""
    return v


def _descricao(av: dict) -> tuple[str, str]:
    """
    (tipo, detalhe) legíveis para o painel.

    O campo `descricao` traz o nome do evento ("Vendaval"); o detalhe
    — intensidade e riscos — costuma estar em `riscos` ou `instrucoes`.
    Procuramos primeiro pelos nomes conhecidos e só depois varremos o resto
    do objeto, sempre passando pelo filtro de prosa.
    """
    tipo = str(av.get("descricao_aviso") or av.get("tipo")
               or av.get("evento") or av.get("event") or "").strip()
    desc = str(av.get("descricao") or av.get("description") or "").strip()
    if not tipo and desc:
        m = re.match(r"aviso de ([^.]+)", desc, flags=re.I)
        tipo = m.group(1).strip() if m else (desc if len(desc) < 60 else "")

    detalhe = ""
    for chave in ("riscos", "instrucoes", "descricao", "instrucao",
                  "aviso_texto", "texto", "description", "instruction",
                  "headline", "observacao"):
        detalhe = _texto_util(av.get(chave))
        if detalhe:
            break
    if not detalhe:
        candidatos = [_texto_util(v) for k, v in av.items()
                      if k not in ("municipios", "estados")]
        candidatos = [c for c in candidatos if c]
        detalhe = min(candidatos, key=len) if candidatos else ""

    detalhe = re.sub(r"^aviso de [^.]+\.\s*", "", detalhe, flags=re.I).strip()
    return (tipo or "Aviso meteorológico"), detalhe


# ──────────────────────────────────────────────────────────────────────────
# Caminho 1 — API de avisos
# ──────────────────────────────────────────────────────────────────────────
def _tentar_api() -> dict | None:
    from coleta.rede import forcar_ipv4
    forcar_ipv4()

    dados = None
    for url in _URLS_API:
        for tentativa in (1, 2):
            try:
                r = requests.get(url, headers=_CABECALHOS, timeout=(8, 20))
                print(f"[INMET] GET {url} → HTTP {r.status_code}")
                r.raise_for_status()
                dados = r.json()
                break
            except Exception as exc:
                print(f"[INMET] tentativa {tentativa}/2 em {url} falhou "
                      f"({str(exc)[:90]})")
                if tentativa == 1:
                    import time as _t
                    _t.sleep(3)
        if dados is not None:
            break
    if dados is None:
        print("[INMET] API indisponível; tentando Selenium.")
        return None

    brutos = _achatar_avisos(dados)
    # Diagnóstico no log do Actions: sem isto, "0 avisos" é ambíguo entre
    # "não há avisos" e "não entendi a resposta".
    formato = (list(dados.keys()) if isinstance(dados, dict)
               else f"lista[{len(dados)}]" if isinstance(dados, list) else type(dados).__name__)
    print(f"[INMET] resposta: {formato} · {len(brutos)} aviso(s) no Brasil")
    if brutos:
        primeiro = brutos[0]
        print(f"[INMET] campos do 1º aviso: {sorted(primeiro.keys())}")
        # amostra CURTA de cada campo — sem isto, acertar nome de campo do
        # INMET vira adivinhação. Cortado em 90 chars p/ não despejar base64.
        for k, v in list(primeiro.items())[:20]:
            amostra = " ".join(str(v).split())[:90]
            print(f"[INMET]     {k} = {amostra}")

    encontrados, futuros = [], []
    for av in brutos:
        criterio = _abrange_poa(av)
        if not criterio:
            continue
        tipo, detalhe = _descricao(av)
        txt_ini, dt_ini = _quando(av, _CAMPOS_INICIO, "inicio")
        txt_fim, dt_fim = _quando(av, _CAMPOS_FIM, "fim")
        registro = {
            "severidade": _severidade(av),
            "tipo": tipo,
            "descricao": tipo,          # compatibilidade com o painel antigo
            "detalhe": detalhe,
            "inicio": txt_ini or None,
            "fim": txt_fim or None,
            "criterio": criterio,
        }
        if _vigente_hoje(dt_ini, dt_fim):
            encontrados.append(registro)
        else:
            futuros.append(registro)

    # Dois avisos idênticos (mesmo evento em áreas vizinhas) viram um só.
    unicos, chaves = [], set()
    for a in encontrados:
        chave = (a["severidade"], a["tipo"], a["inicio"], a["fim"])
        if chave in chaves:
            continue
        chaves.add(chave)
        unicos.append(a)

    if futuros:
        print(f"[INMET] {len(futuros)} aviso(s) de POA fora do dia de hoje "
              f"(não entram no painel nem na classificação): "
              + "; ".join(f"{f['severidade']}/{f['tipo']} {f['inicio']}→{f['fim']}"
                          for f in futuros[:4]))
    return {"alertas": unicos, "alertas_futuros": futuros,
            "fonte": "api", "consultado": True}


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
        candidatos = driver.find_elements(
            By.CSS_SELECTOR,
            "table tr, .card, [class*='aviso'], [class*='alert'], [class*='warning']",
        )
        termos = ("porto alegre", "metropolitana", "rio grande do sul")
        for el in candidatos:
            texto = el.text.strip()
            if not texto or len(texto) < 15:
                continue
            texto_l = texto.lower()
            if not any(t in texto_l for t in termos):
                continue
            sev = None
            if "grande perigo" in texto_l or "vermelho" in texto_l:
                sev = "Vermelho"
            elif "perigo potencial" in texto_l or "amarelo" in texto_l:
                sev = "Amarelo"
            elif re.search(r"\bperigo\b", texto_l) or "laranja" in texto_l:
                sev = "Laranja"
            if sev:
                encontrados.append({
                    "severidade": sev, "tipo": "",
                    "descricao": texto[:120], "detalhe": texto[:400],
                    "inicio": None, "fim": None,
                    "criterio": "texto da página de alertas",
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
    """Coleta avisos vigentes do INMET para POA (API → reserva Selenium)."""
    resultado = _tentar_api()
    if resultado is None:
        resultado = _scrape_selenium()

    alertas = resultado.get("alertas") or []
    max_sev = None
    if alertas:
        max_sev = max(alertas,
                      key=lambda a: _ORDEM_SEVERIDADE.get(a["severidade"], 0))["severidade"]

    resultado["max_severidade"] = max_sev
    print(f"[INMET] {len(alertas)} aviso(s) p/ Porto Alegre | máx: {max_sev} "
          f"| fonte: {resultado.get('fonte')}")
    for a in alertas[:5]:
        print(f"[INMET]   · {a['severidade']} — {a.get('tipo')} "
              f"| {a.get('inicio')} → {a.get('fim')} | {a.get('criterio')}")
    return resultado


if __name__ == "__main__":
    print(json.dumps(coletar_alertas_inmet(), ensure_ascii=False, indent=2))
