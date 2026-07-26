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
    codigo = codigo or config.INMET_ESTACAO_POA
    fim = datetime.now().date()
    inicio = fim - timedelta(days=dias)
    url = (f"https://apitempo.inmet.gov.br/estacao/"
           f"{inicio:%Y-%m-%d}/{fim:%Y-%m-%d}/{codigo}")

    vazio = {
        "horaria": pd.DataFrame(columns=["datahora", "precipitacao_mm"]),
        "diaria": pd.DataFrame(columns=["data", "precipitacao_total_mm"]),
        "acumulado_24h_mm": None, "acumulado_72h_mm": None,
        "acumulado_7d_mm": None, "estacao": codigo,
        "fonte": "INMET (estação automática)", "ok": False,
    }

    registros = None
    for tentativa in (1, 2):
        try:
            r = requests.get(url, headers=_CABECALHOS, timeout=30)
            r.raise_for_status()
            registros = r.json()
            break
        except Exception as exc:
            print(f"[INMET-estação] tentativa {tentativa}/2 falhou ({exc})")
            if tentativa == 2:
                print("[INMET-estação] indisponível; usando Open-Meteo como reserva.")
                return vazio
            import time
            time.sleep(3)

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
