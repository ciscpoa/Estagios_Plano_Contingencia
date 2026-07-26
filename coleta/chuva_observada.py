# -*- coding: utf-8 -*-
"""
chuva_observada.py
==================
CHUVA JÁ OCORRIDA em Porto Alegre — fonte única e auditável.

Por que este módulo existe
--------------------------
Até 26/07/2026 a chuva observada vinha do pluviômetro da estação
FLUVIOMÉTRICA da ANA no Cais Mauá (87450004). Essa estação existe para
medir NÍVEL do Guaíba; o pluviômetro dela transmite de forma esparsa e
subestimou grosseiramente a chuva da semana (≈2 mm/dia num período em
que choveu muito em POA). Um acumulado errado derruba os gatilhos de
chuva do Plano e o estágio sai errado.

A correção tem duas partes:

1. CADEIA DE FONTES, da mais fiel à menos fiel:
     1º INMET  — estação automática (pluviômetro em solo, série horária).
                 As estações são DESCOBERTAS pela API, por proximidade de
                 POA: se a A801 sair do ar (o INMET está trocando as
                 estações do RS ao longo de 2025/2026), a próxima estação
                 operante mais perto assume sozinha.
     2º CEMADEN — pluviômetros automáticos da rede federal em POA.
     3º ANA     — pluviômetros telemétricos (só se passarem no controle).
     4º Open-Meteo — modelo global, último recurso e sempre rotulado.

2. PORTEIRO DE QUALIDADE (`_avaliar`): nenhuma série entra no painel sem
   passar por cobertura mínima de horas e por uma comparação contra uma
   referência independente. Uma série que reporta 12 mm em 7 dias quando
   a referência aponta 90 mm é REJEITADA e registrada no log — foi
   exatamente esse o caso do Cais Mauá.

Saída (mesmo formato de antes, com campos novos de auditoria):
    {
      "ok", "fonte", "estacao", "horaria", "diaria",
      "acumulado_24h_mm", "acumulado_72h_mm", "acumulado_7d_mm",
      "dias_com_chuva_5d", "dias_chuva_intensa_5d",
      "qualidade": {...}, "tentativas": [ {...}, ... ]
    }
"""

from __future__ import annotations

import math
import os
from datetime import datetime, timedelta

import pandas as pd
import requests

import config

try:                                    # o projeto já força IPv4 p/ gov.br
    from coleta.rede import forcar_ipv4
except Exception:                       # pragma: no cover
    def forcar_ipv4():                  # type: ignore
        return None


_CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "application/json, text/plain, */*",
}

COLUNAS_HORARIA = ["datahora", "precipitacao_mm"]


# ══════════════════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════════════════
def _vazio(fonte: str = "—", estacao=None) -> dict:
    return {
        "ok": False, "fonte": fonte, "fonte_curta": _curto(fonte),
        "estacao": estacao,
        "horaria": pd.DataFrame(columns=COLUNAS_HORARIA),
        "diaria": pd.DataFrame(columns=["data", "precipitacao_total_mm"]),
        "acumulado_24h_mm": None, "acumulado_72h_mm": None,
        "acumulado_96h_mm": None,
        "acumulado_7d_mm": None, "dias_com_chuva_5d": 0,
        "dias_chuva_intensa_5d": 0, "qualidade": {}, "tentativas": [],
    }


def _num(valor) -> float | None:
    if valor in (None, "", "null", "-", "None"):
        return None
    try:
        v = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None
    # sentinelas comuns de dado ausente nas APIs meteorológicas
    if not math.isfinite(v) or v < 0 or v > 500:
        return None
    return v


def _dist_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância aproximada (haversine) em km."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _curto(fonte: str) -> str:
    """
    Nome curto da fonte para exibição: 'ANA · Gravataí' em vez de
    'ANA Gravataí (Passo das Canoas) (pluviômetro telemétrico)'.
    O nome completo continua no CSV e no log, para auditoria.
    """
    f = (fonte or "").strip()
    if f.startswith("INMET"):
        resto = f.replace("INMET", "", 1).strip(" —-")
        # "A801 — PORTO ALEGRE - JARDIM BOTANICO" → "Porto Alegre"
        if "—" in resto:
            resto = resto.split("—", 1)[1]
        local = resto.split(" - ")[0].strip().title()
        return f"INMET — {local}" if local else "INMET"
    if f.startswith("ANA"):
        resto = f.replace("ANA", "", 1).strip()
        local = resto.split(" (")[0].strip()
        return f"ANA — {local}" if local else "ANA"
    if f.startswith("CEMADEN"):
        return "CEMADEN — Porto Alegre"
    if f.startswith("Open-Meteo"):
        return "Open-Meteo (modelo global)"
    return f or "—"


def _fechar(horaria: pd.DataFrame, fonte: str, estacao) -> dict:
    """Monta o dicionário-padrão a partir de uma série horária limpa."""
    if horaria is None or horaria.empty:
        return _vazio(fonte, estacao)

    h = (horaria.dropna(subset=["precipitacao_mm"])
         .drop_duplicates(subset="datahora")
         .sort_values("datahora")
         .reset_index(drop=True))
    if h.empty:
        return _vazio(fonte, estacao)

    diaria = (h.assign(data=h["datahora"].dt.normalize())
              .groupby("data", as_index=False)["precipitacao_mm"].sum()
              .rename(columns={"precipitacao_mm": "precipitacao_total_mm"}))

    # Âncora = AGORA, não a última leitura. Se a estação parou de transmitir
    # há 3 dias, o "acumulado 24h" tem de ser 0 e não a chuva de 3 dias atrás.
    agora = pd.Timestamp.now()

    def acum(horas: int) -> float:
        corte = agora - pd.Timedelta(hours=horas)
        return round(float(h.loc[h["datahora"] >= corte, "precipitacao_mm"].sum()), 1)

    limiar_int = config.LIMIARES_CHUVA["acumulado_24h_intensa"]
    limiar_dia = config.LIMIARES_CHUVA.get("dia_com_chuva_relevante", 5.0)
    dias_com_chuva = dias_intensos = 0
    for _, total in diaria.tail(5)[["data", "precipitacao_total_mm"]].values:
        if total >= limiar_dia:
            dias_com_chuva += 1
        if total >= limiar_int:
            dias_intensos += 1

    return {
        "ok": True, "fonte": fonte, "fonte_curta": _curto(fonte), "estacao": estacao,
        "horaria": h, "diaria": diaria,
        "acumulado_24h_mm": acum(24),
        "acumulado_72h_mm": acum(72),
        # 96h é a janela de CONVENÇÃO do painel: é o que aparece no banner
        # e na árvore, para não poluir a leitura com três números.
        "acumulado_96h_mm": acum(96),
        "acumulado_7d_mm": acum(24 * 7),
        "dias_com_chuva_5d": dias_com_chuva,
        "dias_chuva_intensa_5d": dias_intensos,
        "qualidade": {}, "tentativas": [],
    }


# ══════════════════════════════════════════════════════════════════════════
# PORTEIRO DE QUALIDADE
# ══════════════════════════════════════════════════════════════════════════
def _avaliar(cand: dict, referencia_7d_mm: float | None, dias: int,
             cobertura_minima: float | None = None) -> dict:
    """
    Decide se uma série pode virar a chuva observada oficial do painel.

    Critérios:
      • COBERTURA: horas com leitura / horas da janela. Um pluviômetro que
        transmitiu 20 das 168 horas não serve para calcular acumulado.
        O limiar vem de `cobertura_minima` (o coletor faz duas passadas:
        uma exigente e, se nada passar, uma com o piso absoluto).
      • PLAUSIBILIDADE: o total de 7 dias comparado a uma referência
        independente (Open-Meteo). Se a candidata reporta menos de
        `RAZAO_MINIMA` da referência E a referência é significativa,
        a série está subestimando e é rejeitada.

    Devolve {"aprovada": bool, "motivo": str, ...}.
    """
    q = {"aprovada": False, "motivo": "", "cobertura_pct": None,
         "total_7d_mm": None, "referencia_7d_mm": referencia_7d_mm,
         "razao_vs_referencia": None}

    if not cand.get("ok"):
        q["motivo"] = "sem dados"
        return q

    h = cand["horaria"]
    horas_janela = max(1, dias * 24)
    # nº de horas distintas com leitura (a série pode ser sub-horária)
    horas_com_dado = h["datahora"].dt.floor("h").nunique()
    cobertura = 100.0 * min(1.0, horas_com_dado / horas_janela)
    q["cobertura_pct"] = round(cobertura, 1)

    total = cand.get("acumulado_7d_mm") or 0.0
    q["total_7d_mm"] = total

    cob_min = (cobertura_minima if cobertura_minima is not None
               else config.QUALIDADE_CHUVA["cobertura_minima_pct"])
    q["cobertura_minima_pct"] = cob_min
    if cobertura < cob_min:
        q["motivo"] = (f"cobertura de apenas {cobertura:.0f}% das horas "
                       f"(mínimo {cob_min:.0f}%) — acumulados não confiáveis")
        return q

    ref = referencia_7d_mm
    if ref is not None and ref >= config.QUALIDADE_CHUVA["referencia_minima_mm"]:
        razao = (total / ref) if ref else 0.0
        q["razao_vs_referencia"] = round(razao, 2)
        minimo = config.QUALIDADE_CHUVA["razao_minima_vs_referencia"]
        maximo = config.QUALIDADE_CHUVA["razao_maxima_vs_referencia"]
        if razao < minimo:
            q["motivo"] = (f"{total:.0f} mm/7d contra referência de {ref:.0f} mm "
                           f"({razao:.0%} do esperado) — série subestimando")
            return q
        if razao > maximo:
            q["motivo"] = (f"{total:.0f} mm/7d contra referência de {ref:.0f} mm "
                           f"({razao:.0%}) — série provavelmente acumulada/duplicada")
            return q

    q["aprovada"] = True
    q["motivo"] = f"{total:.0f} mm/7d · cobertura {cobertura:.0f}%"
    return q


# ══════════════════════════════════════════════════════════════════════════
# FONTE 1 — INMET (estação automática, com auto-descoberta)
# ══════════════════════════════════════════════════════════════════════════
_BASE_INMET = "https://apitempo.inmet.gov.br"
_CACHE_ESTACOES: dict = {"lista": None}


def _token_inmet() -> str:
    return (os.environ.get("INMET_TOKEN") or "").strip()


def _url_inmet(caminho: str) -> str:
    tk = _token_inmet()
    return f"{_BASE_INMET}/token/{caminho}/{tk}" if tk else f"{_BASE_INMET}/{caminho}"


def estacoes_inmet_proximas(limite: int = 6, raio_km: float = 120.0) -> list[dict]:
    """
    Descobre as estações automáticas do INMET mais próximas de Porto Alegre.

    Consulta o inventário em /estacoes/T e ordena por distância. Assim o
    painel NÃO depende de um código fixo: quando o INMET tira a A801 do ar
    para trocar o equipamento, a estação seguinte assume automaticamente.
    """
    if _CACHE_ESTACOES["lista"] is not None:
        lista = _CACHE_ESTACOES["lista"]
    else:
        forcar_ipv4()
        lista = []
        try:
            r = requests.get(_url_inmet("estacoes/T"), headers=_CABECALHOS,
                             timeout=(10, 30))
            r.raise_for_status()
            lista = r.json() or []
        except Exception as exc:
            print(f"[INMET] inventário de estações indisponível ({str(exc)[:80]}).")
        _CACHE_ESTACOES["lista"] = lista

    candidatas = []
    for est in lista:
        if not isinstance(est, dict):
            continue
        uf = (est.get("SG_ESTADO") or "").upper()
        situacao = (est.get("CD_SITUACAO") or "").lower()
        if uf and uf != "RS":
            continue
        if situacao and "pane" in situacao:
            continue
        # coordenadas são negativas em POA — parser próprio, não o _num()
        lat = _num_coord(est.get("VL_LATITUDE"))
        lon = _num_coord(est.get("VL_LONGITUDE"))
        if lat is None or lon is None:
            continue
        d = _dist_km(config.POA_LAT, config.POA_LON, lat, lon)
        if d > raio_km:
            continue
        candidatas.append({
            "codigo": est.get("CD_ESTACAO"),
            "nome": est.get("DC_NOME") or est.get("CD_ESTACAO"),
            "dist_km": round(d, 1),
        })

    candidatas.sort(key=lambda e: e["dist_km"])
    # a estação configurada tem prioridade se estiver na lista
    preferida = getattr(config, "INMET_ESTACAO_POA", None)
    if preferida:
        candidatas.sort(key=lambda e: (e["codigo"] != preferida, e["dist_km"]))
        if not any(e["codigo"] == preferida for e in candidatas):
            candidatas.insert(0, {"codigo": preferida, "nome": preferida,
                                  "dist_km": 0.0})
    return candidatas[:limite]


def _num_coord(valor) -> float | None:
    """Coordenadas podem ser negativas — _num() as descarta, então aqui é separado."""
    if valor in (None, "", "null"):
        return None
    try:
        v = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _serie_inmet(codigo: str, dias: int) -> pd.DataFrame:
    """Série horária de chuva de UMA estação automática do INMET."""
    fim = datetime.now().date()
    inicio = fim - timedelta(days=dias)
    ontem = fim - timedelta(days=1)

    janelas = [
        ("horária até hoje", f"estacao/{inicio:%Y-%m-%d}/{fim:%Y-%m-%d}/{codigo}"),
        ("horária até ontem", f"estacao/{inicio:%Y-%m-%d}/{ontem:%Y-%m-%d}/{codigo}"),
    ]
    ultimo_status = None
    for rotulo, caminho in janelas:
        try:
            r = requests.get(_url_inmet(caminho), headers=_CABECALHOS,
                             timeout=(10, 30))
            ultimo_status = r.status_code
            if r.status_code == 204 or not (r.text or "").strip():
                print(f"[INMET] {codigo} ({rotulo}): HTTP {r.status_code} sem conteúdo")
                continue
            if r.status_code in (401, 403):
                print(f"[INMET] {codigo} ({rotulo}): HTTP {r.status_code} — "
                      "endpoint exige chave (defina o secret INMET_TOKEN)")
                continue
            r.raise_for_status()
            registros = r.json() or []
        except Exception as exc:
            print(f"[INMET] {codigo} ({rotulo}): {str(exc)[:70]}")
            continue

        linhas = []
        for reg in registros:
            data = reg.get("DT_MEDICAO") or reg.get("DTMEDICAO")
            hora = reg.get("HR_MEDICAO") or reg.get("HRMEDICAO")
            chuva = _num(reg.get("CHUVA") if reg.get("CHUVA") is not None
                         else reg.get("CHUVA_INS") or reg.get("PRE_INS"))
            if not data or hora is None:
                continue
            hora_txt = str(hora).replace(":", "").zfill(4)[:4]
            try:
                quando = datetime.strptime(f"{data} {hora_txt}", "%Y-%m-%d %H%M")
            except ValueError:
                continue
            linhas.append({"datahora": quando - timedelta(hours=3),   # UTC → POA
                           "precipitacao_mm": chuva if chuva is not None else 0.0})
        if linhas:
            return pd.DataFrame(linhas)
    _ULTIMO_STATUS_INMET["codigo"] = ultimo_status
    return pd.DataFrame(columns=COLUNAS_HORARIA)


_ULTIMO_STATUS_INMET: dict = {"codigo": None}


def fonte_inmet(dias: int = 7, referencia_7d_mm: float | None = None) -> list[dict]:
    """
    Devolve TODAS as candidatas do INMET já avaliadas (a decisão de qual
    usar fica com `coletar()`, que compara as fontes entre si).
    """
    saidas = []
    for est in estacoes_inmet_proximas():
        df = _serie_inmet(est["codigo"], dias)
        rotulo = f"INMET {est['codigo']} — {est['nome']}"
        cand = _fechar(df, rotulo, est["codigo"])
        cand["qualidade"] = _avaliar(cand, referencia_7d_mm, dias)
        if not cand["qualidade"]["aprovada"] and df.empty:
            st = _ULTIMO_STATUS_INMET.get("codigo")
            if st in (401, 403):
                cand["qualidade"]["motivo"] = (
                    f"HTTP {st} — endpoint exige chave (secret INMET_TOKEN)")
            elif st == 204:
                cand["qualidade"]["motivo"] = "HTTP 204 — estação sem transmitir"
            elif st:
                cand["qualidade"]["motivo"] = f"HTTP {st} — sem dados"
        cand["dist_km"] = est["dist_km"]
        saidas.append(cand)
        if cand["qualidade"]["aprovada"]:
            print(f"[INMET] ✔ {rotulo} ({est['dist_km']} km) — "
                  f"{cand['qualidade']['motivo']}")
            break
        print(f"[INMET] ✖ {rotulo}: {cand['qualidade']['motivo'] or 'sem dados'}")
    return saidas


# ══════════════════════════════════════════════════════════════════════════
# FONTE 2 — CEMADEN (pluviômetros automáticos da rede federal)
# ══════════════════════════════════════════════════════════════════════════
def fonte_cemaden(dias: int = 7, referencia_7d_mm: float | None = None) -> dict:
    """
    Pluviômetros automáticos do CEMADEN em Porto Alegre.

    ATENÇÃO: o endpoint do Mapa Interativo não é uma API documentada — o
    formato pode mudar sem aviso. Por isso o parser é tolerante e, se não
    reconhecer o retorno, devolve ok=False sem quebrar a coleta. Confira a
    URL em `config.CEMADEN_URL_JSON` se esta fonte parar de responder.
    """
    if not getattr(config, "CEMADEN_ATIVO", True):
        return _vazio("CEMADEN (desativado)")

    forcar_ipv4()
    try:
        r = requests.get(config.CEMADEN_URL_JSON, headers=_CABECALHOS,
                         timeout=(10, 30))
        r.raise_for_status()
        dados = r.json()
    except Exception as exc:
        print(f"[CEMADEN] indisponível ({str(exc)[:80]}).")
        return _vazio("CEMADEN")

    # O retorno já foi visto como lista direta e como {"estacoes": [...]}
    if isinstance(dados, dict):
        for chave in ("estacoes", "dados", "items", "features"):
            if isinstance(dados.get(chave), list):
                dados = dados[chave]
                break
    if not isinstance(dados, list):
        print("[CEMADEN] formato de retorno não reconhecido.")
        return _vazio("CEMADEN")

    linhas: list[dict] = []
    nomes: set[str] = set()
    for est in dados:
        if not isinstance(est, dict):
            continue
        cidade = str(est.get("cidade") or est.get("municipio")
                     or est.get("nomeMunicipio") or "")
        if "porto alegre" not in cidade.lower():
            continue
        nome = str(est.get("nomeEstacao") or est.get("nome")
                   or est.get("estacao") or "estação")
        # série temporal, quando vier
        serie = (est.get("valores") or est.get("dados")
                 or est.get("medicoes") or [])
        for ponto in serie if isinstance(serie, list) else []:
            if not isinstance(ponto, dict):
                continue
            quando = (ponto.get("datahora") or ponto.get("dataHora")
                      or ponto.get("data"))
            valor = _num(ponto.get("valor") if ponto.get("valor") is not None
                         else ponto.get("chuva") or ponto.get("acumulado"))
            if quando is None or valor is None:
                continue
            try:
                dh = pd.to_datetime(quando)
            except Exception:
                continue
            if dh.tzinfo is not None:
                dh = dh.tz_convert(None) if hasattr(dh, "tz_convert") else dh
            # CEMADEN publica em UTC
            linhas.append({"datahora": dh - pd.Timedelta(hours=3),
                           "precipitacao_mm": valor, "estacao": nome})
        nomes.add(nome)

    if not linhas:
        if nomes:
            print(f"[CEMADEN] {len(nomes)} pluviômetro(s) em POA, mas sem série "
                  "temporal no retorno (o endpoint devolveu só o instantâneo).")
        else:
            print("[CEMADEN] nenhum pluviômetro de Porto Alegre no retorno.")
        return _vazio("CEMADEN")

    df = pd.DataFrame(linhas)
    # média entre pluviômetros da cidade, hora a hora — é o "quanto choveu
    # em média em POA" que o painel precisa, e não o extremo de um ponto só
    df["hora"] = df["datahora"].dt.floor("h")
    media = (df.groupby(["hora", "estacao"], as_index=False)["precipitacao_mm"].sum()
               .groupby("hora", as_index=False)["precipitacao_mm"].mean()
               .rename(columns={"hora": "datahora"}))

    rotulo = f"CEMADEN — média de {len(nomes)} pluviômetro(s) em POA"
    cand = _fechar(media, rotulo, "CEMADEN/POA")
    cand["qualidade"] = _avaliar(cand, referencia_7d_mm, dias)
    print(f"[CEMADEN] {'✔' if cand['qualidade']['aprovada'] else '✖'} {rotulo}: "
          f"{cand['qualidade']['motivo']}")
    return cand


# ══════════════════════════════════════════════════════════════════════════
# FONTE 3 — ANA (pluviômetros telemétricos)
# ══════════════════════════════════════════════════════════════════════════
def fonte_ana(rios: dict, dias: int = 7,
              referencia_7d_mm: float | None = None) -> list[dict]:
    """
    Aproveita as séries da ANA que a coleta de níveis já baixou.

    IMPORTANTE: a estação do Cais Mauá é FLUVIOMÉTRICA. O pluviômetro dela
    transmite de forma esparsa e subestima a chuva — por isso ela sai da
    frente da fila e, como todas as demais, só entra no painel se passar
    no porteiro de qualidade.
    """
    ordem = [n for n in getattr(config, "ANA_ORDEM_PLUVIOMETROS", []) if n in rios]
    ordem += [n for n in rios if n not in ordem]

    saidas = []
    for nome in ordem:
        df = rios.get(nome)
        if df is None or df.empty or "chuva_mm" not in df:
            continue
        serie = (df.dropna(subset=["chuva_mm"])[["datahora", "chuva_mm"]]
                 .rename(columns={"chuva_mm": "precipitacao_mm"}))
        if serie.empty or float(serie["precipitacao_mm"].sum()) <= 0:
            continue

        rotulo = f"ANA {config.NOMES_EXIBICAO.get(nome, nome)} (pluviômetro telemétrico)"
        cand = _fechar(serie, rotulo, nome)
        cand["qualidade"] = _avaliar(cand, referencia_7d_mm, dias)
        saidas.append(cand)
        if cand["qualidade"]["aprovada"]:
            print(f"[ANA-chuva] ✔ {rotulo} — {cand['qualidade']['motivo']}")
            break
        print(f"[ANA-chuva] ✖ {rotulo}: {cand['qualidade']['motivo']}")
    return saidas


# ══════════════════════════════════════════════════════════════════════════
# FONTE 4 — Open-Meteo (reserva declarada)
# ══════════════════════════════════════════════════════════════════════════
def fonte_open_meteo(meteo: dict, dias: int = 7) -> dict:
    """Série observada do Open-Meteo (past_days). Modelo global — reserva."""
    h = (meteo or {}).get("horaria")
    if h is None or h.empty:
        return _vazio("Open-Meteo")
    agora = pd.Timestamp.now()
    passado = h[h["datahora"] <= agora][["datahora", "precipitacao_mm"]]
    cand = _fechar(passado, "Open-Meteo (modelo global — reserva)", "open-meteo")
    cand["qualidade"] = {"aprovada": True, "motivo": "fonte de reserva",
                         "cobertura_pct": 100.0,
                         "total_7d_mm": cand.get("acumulado_7d_mm")}
    return cand


# ══════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR
# ══════════════════════════════════════════════════════════════════════════
def coletar(rios: dict | None = None, meteo: dict | None = None,
            dias: int = 7) -> dict:
    """
    Roda a cadeia de fontes em DUAS PASSADAS e devolve a melhor série.

      1ª passada — cobertura exigente (`cobertura_minima_pct`, 80%).
      2ª passada — se nenhuma fonte em solo alcançou os 80%, reavalia as
                   MESMAS candidatas já baixadas com o piso absoluto (45%).
                   Nenhuma requisição nova é feita aqui.
      3ª          — Open-Meteo, sempre rotulado como modelo global.

    A 2ª passada existe para que apertar a régua de qualidade nunca piore o
    painel: um pluviômetro com 60% de cobertura continua sendo informação de
    solo, e melhor que um modelo global.

    `rios`  — saída de ana_api.coletar_niveis_rios() (reaproveitada)
    `meteo` — saída de open_meteo.coletar_previsao()  (referência + reserva)
    """
    rios = rios or {}
    reserva = fonte_open_meteo(meteo or {}, dias)
    referencia = reserva.get("acumulado_7d_mm")
    if referencia:
        print(f"[CHUVA] referência independente p/ controle de qualidade: "
              f"{referencia:.0f} mm/7d (Open-Meteo)")

    def _registro(cand: dict) -> dict:
        q = cand.get("qualidade") or {}
        return {"fonte": cand.get("fonte"), "total_7d_mm": q.get("total_7d_mm"),
                "cobertura_pct": q.get("cobertura_pct"),
                "aprovada": q.get("aprovada", False), "motivo": q.get("motivo")}

    # ── 1ª passada: exigente ────────────────────────────────────────────
    candidatas: list[dict] = []
    tentativas: list[dict] = []
    for grupo in (fonte_inmet(dias, referencia),
                  [fonte_cemaden(dias, referencia)],
                  fonte_ana(rios, dias, referencia)):
        for cand in grupo:
            candidatas.append(cand)
            tentativas.append(_registro(cand))
            if (cand.get("qualidade") or {}).get("aprovada"):
                cand["tentativas"] = tentativas
                print(f"[CHUVA] >>> observada adotada: {cand['fonte']} · "
                      f"24h={cand['acumulado_24h_mm']:.0f} mm · "
                      f"72h={cand['acumulado_72h_mm']:.0f} mm · "
                      f"7d={cand['acumulado_7d_mm']:.0f} mm")
                return cand

    # ── 2ª passada: mesmas candidatas, piso absoluto ────────────────────
    piso = config.QUALIDADE_CHUVA["cobertura_minima_absoluta_pct"]
    exigido = config.QUALIDADE_CHUVA["cobertura_minima_pct"]
    print(f"[CHUVA] nenhuma fonte alcançou {exigido:.0f}% de cobertura — "
          f"2ª passada com o piso de {piso:.0f}%.")
    # a de maior cobertura primeiro: entre séries incompletas, a mais densa vence
    for cand in sorted(candidatas, key=lambda c: -((c.get("qualidade") or {})
                                                   .get("cobertura_pct") or 0)):
        q = _avaliar(cand, referencia, dias, cobertura_minima=piso)
        if q["aprovada"]:
            q["motivo"] += f" (aceita na 2ª passada, abaixo dos {exigido:.0f}% ideais)"
            cand["qualidade"] = q
            tentativas.append(_registro(cand))
            cand["tentativas"] = tentativas
            print(f"[CHUVA] >>> observada adotada (2ª passada): {cand['fonte']} · "
                  f"{q['motivo']}")
            return cand

    tentativas.append({"fonte": reserva.get("fonte"),
                       "total_7d_mm": reserva.get("acumulado_7d_mm"),
                       "cobertura_pct": 100.0, "aprovada": True,
                       "motivo": "reserva — nenhuma fonte em solo passou"})
    reserva["tentativas"] = tentativas
    print("[CHUVA] ⚠ nenhuma estação em solo passou no controle de qualidade — "
          f"usando {reserva['fonte']}.")
    return reserva


if __name__ == "__main__":
    from coleta import open_meteo
    m = open_meteo.coletar_previsao()
    saida = coletar(meteo=m)
    print("\nFonte adotada:", saida["fonte"])
    print("Acumulados:", saida["acumulado_24h_mm"], saida["acumulado_72h_mm"],
          saida["acumulado_7d_mm"])
    for t in saida["tentativas"]:
        print("  •", t)
