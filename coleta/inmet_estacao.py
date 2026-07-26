# -*- coding: utf-8 -*-
"""
inmet_estacao.py
================
Chuva OBSERVADA em Porto Alegre, medida pela estação meteorológica
automática do INMET (dado de pluviômetro na cidade, não modelo global).

Endpoint (API pública do INMET):
    https://apitempo.inmet.gov.br/estacao/{inicio}/{fim}/{codigo}

Cada registro traz, entre outros campos:
    DTMEDICAO  → "2026-07-26"   (data da medição, UTC)
    HRMEDICAO  → "1300"         (hora UTC, formato HHMM)
    CHUVA      → "2.4"          (chuva acumulada na hora, em mm)
    TEM_INS/TEMINS, UMD_INS/UMDINS, VEN_VEL/VENVEL → temperatura/umidade/vento

Motivação: o Open-Meteo é um modelo global e diverge do que a Defesa Civil
de POA usa. Aqui a chuva observada passa a vir de um pluviômetro na cidade.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import requests

import config
from coleta.rede import cabecalhos_navegador, forcar_ipv4

_CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36"),
    "Accept": "application/json",
    "Referer": "https://tempo.inmet.gov.br/",
}


def _para_float(valor) -> float | None:
    if valor in (None, "", "null"):
        return None
    try:
        return float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _campo(reg: dict, *nomes) -> object:
    """A API alterna nomes (CHUVA/CHUVA_INS, TEMINS/TEM_INS...)."""
    for nome in nomes:
        if nome in reg and reg[nome] not in (None, ""):
            return reg[nome]
    return None


def coletar_chuva_observada(dias: int = 7, codigo: str | None = None) -> dict:
    """
    Retorna:
      {
        "horaria": DataFrame [datahora, precipitacao_mm],
        "diaria":  DataFrame [data, precipitacao_total_mm],
        "acumulado_24h_mm", "acumulado_72h_mm", "acumulado_7d_mm",
        "estacao", "fonte", "ok"
      }
    Em caso de falha, devolve estruturas vazias com ok=False (o pipeline
    segue usando o Open-Meteo como reserva).
    """
    import os

    codigo = codigo or config.INMET_ESTACAO_POA
    fim = datetime.now().date()
    inicio = fim - timedelta(days=dias)

    # O INMET passou a exigir token em parte dos endpoints. Tentamos primeiro
    # o endpoint aberto; havendo INMET_TOKEN definido, tentamos também o
    # endpoint autenticado. Peça a chave em: https://portal.inmet.gov.br
    token = (os.environ.get("INMET_TOKEN") or "").strip()

    # O INMET devolveu HTTP 204 (sem conteúdo) para a janela terminando hoje.
    # Tentamos algumas combinações antes de desistir:
    #   • janela terminando ONTEM (o dado do dia corrente às vezes não existe)
    #   • janela curta (3 dias)
    #   • endpoint /estacao/diaria (agregado por dia)
    ontem = fim - timedelta(days=1)
    janelas = [
        ("horária, últimos dias", "estacao", inicio, fim),
        ("horária, até ontem", "estacao", inicio, ontem),
        ("horária, 3 dias", "estacao", fim - timedelta(days=3), ontem),
        ("diária, últimos dias", "estacao/diaria", inicio, ontem),
    ]

    def _url(prefixo: str, ini, f) -> str:
        base = "https://apitempo.inmet.gov.br"
        if token:
            return f"{base}/token/{prefixo}/{ini:%Y-%m-%d}/{f:%Y-%m-%d}/{codigo}/{token}"
        return f"{base}/{prefixo}/{ini:%Y-%m-%d}/{f:%Y-%m-%d}/{codigo}"

    vazio = {
        "horaria": pd.DataFrame(columns=["datahora", "precipitacao_mm"]),
        "diaria": pd.DataFrame(columns=["data", "precipitacao_total_mm"]),
        "acumulado_24h_mm": None, "acumulado_72h_mm": None,
        "acumulado_7d_mm": None, "estacao": codigo,
        "fonte": "INMET (estação automática)", "ok": False,
    }

    forcar_ipv4()      # sem isso, apitempo.inmet.gov.br dá timeout em CI
    registros = None
    for rotulo, prefixo, ini, f in janelas:
        url = _url(prefixo, ini, f)
        try:
            r = requests.get(url, headers=_CABECALHOS, timeout=(10, 25))
            corpo = (r.text or "").strip()
            if r.status_code == 204 or not corpo:
                print(f"[INMET-estação] {rotulo}: HTTP {r.status_code} sem conteúdo.")
                continue
            r.raise_for_status()
            dados = r.json()
            if not dados:
                print(f"[INMET-estação] {rotulo}: lista vazia.")
                continue
            registros = dados
            print(f"[INMET-estação] {rotulo}: OK ({len(dados)} registros)"
                  + (" [com token]" if token else ""))
            break
        except ValueError:
            print(f"[INMET-estação] {rotulo}: resposta não é JSON "
                  f"({corpo[:60]!r}).")
        except Exception as exc:
            print(f"[INMET-estação] {rotulo}: falhou ({str(exc)[:90]}).")

    if registros is None:
        if not token:
            print(f"[INMET-estação] Nenhuma janela retornou dados para "
                  f"{codigo}. O endpoint pode exigir chave (secret "
                  "INMET_TOKEN) ou a estação pode estar sem transmitir. "
                  "Seguindo com as estações do Poaclima / Open-Meteo.")
        else:
            print(f"[INMET-estação] Nenhuma janela retornou dados para "
                  f"{codigo}, mesmo com token.")
        return vazio

    if not registros:
        print("[INMET-estação] resposta vazia; usando Open-Meteo como reserva.")
        return vazio

    linhas = []
    for reg in registros:
        data = _campo(reg, "DT_MEDICAO", "DTMEDICAO")
        hora = _campo(reg, "HR_MEDICAO", "HRMEDICAO")
        chuva = _para_float(_campo(reg, "CHUVA", "CHUVA_INS", "PRE_INS"))
        if data is None or hora is None:
            continue
        hora_txt = str(hora).zfill(4).replace(":", "")[:4]
        try:
            quando = datetime.strptime(f"{data} {hora_txt}", "%Y-%m-%d %H%M")
        except ValueError:
            continue
        # a API entrega em UTC; POA = UTC-3
        linhas.append({"datahora": quando - timedelta(hours=3),
                       "precipitacao_mm": chuva if chuva is not None else 0.0})

    if not linhas:
        print("[INMET-estação] sem registros de chuva utilizáveis.")
        return vazio

    horaria = (pd.DataFrame(linhas)
               .drop_duplicates(subset="datahora")
               .sort_values("datahora")
               .reset_index(drop=True))

    diaria = (horaria.assign(data=horaria["datahora"].dt.normalize())
              .groupby("data", as_index=False)["precipitacao_mm"].sum()
              .rename(columns={"precipitacao_mm": "precipitacao_total_mm"}))

    agora = horaria["datahora"].max()

    def acumulado(horas: int) -> float:
        corte = agora - timedelta(hours=horas)
        return float(horaria.loc[horaria["datahora"] >= corte,
                                 "precipitacao_mm"].sum())

    resultado = {
        "horaria": horaria,
        "diaria": diaria,
        "acumulado_24h_mm": acumulado(24),
        "acumulado_72h_mm": acumulado(72),
        "acumulado_7d_mm": acumulado(24 * 7),
        "estacao": codigo,
        "fonte": "INMET (estação automática)",
        "ok": True,
    }
    print(f"[INMET-estação] {codigo}: {len(horaria)} registros | "
          f"24h={resultado['acumulado_24h_mm']:.1f} mm · "
          f"72h={resultado['acumulado_72h_mm']:.1f} mm · "
          f"7d={resultado['acumulado_7d_mm']:.1f} mm")
    return resultado
