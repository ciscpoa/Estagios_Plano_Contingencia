# -*- coding: utf-8 -*-
"""
open_meteo.py
=============
Consumo da API gratuita Open-Meteo (sem chave) para Porto Alegre:

* Previsão horária/diária de precipitação (próximos 7 dias)
* Chuva observada recente (past_days) — usada como acumulado 24h/72h
* Probabilidade de precipitação e índices de chuva intensa
"""

from __future__ import annotations

import pandas as pd
import requests

import config

URL_FORECAST = "https://api.open-meteo.com/v1/forecast"


def coletar_previsao(past_days: int = 7, forecast_days: int = 7) -> dict:
    """
    Retorna:
      {
        "horaria":  DataFrame[datahora, precipitacao_mm, prob_precip_pct],
        "diaria":   DataFrame[data, precipitacao_total_mm, precip_horas],
        "resumo":   dict com acumulados observados e previstos
      }
    """
    params = {
        "latitude": config.POA_LAT,
        "longitude": config.POA_LON,
        "timezone": config.TIMEZONE,
        "past_days": past_days,
        "forecast_days": forecast_days,
        "hourly": "precipitation,precipitation_probability,rain",
        "daily": "precipitation_sum,precipitation_hours,precipitation_probability_max",
    }
    resp = requests.get(URL_FORECAST, params=params, timeout=30)
    resp.raise_for_status()
    js = resp.json()

    # ── horária ──────────────────────────────────────────────
    h = js["hourly"]
    df_h = pd.DataFrame({
        "datahora": pd.to_datetime(h["time"]),
        "precipitacao_mm": h["precipitation"],
        "prob_precip_pct": h.get("precipitation_probability"),
    })

    # ── diária ───────────────────────────────────────────────
    d = js["daily"]
    df_d = pd.DataFrame({
        "data": pd.to_datetime(d["time"]),
        "precipitacao_total_mm": d["precipitation_sum"],
        "precip_horas": d.get("precipitation_hours"),
        "prob_max_pct": d.get("precipitation_probability_max"),
    })

    resumo = _resumir(df_h)
    return {"horaria": df_h, "diaria": df_d, "resumo": resumo}


def _resumir(df_h: pd.DataFrame) -> dict:
    """Acumulados observados (passado) e previstos (futuro) a partir da série horária."""
    agora = pd.Timestamp.now()
    passado = df_h[df_h["datahora"] <= agora]
    futuro = df_h[df_h["datahora"] > agora]

    def soma(df, horas, col="precipitacao_mm", passado_flag=True):
        if df.empty:
            return 0.0
        if passado_flag:
            corte = agora - pd.Timedelta(hours=horas)
            return float(df[df["datahora"] >= corte][col].sum())
        corte = agora + pd.Timedelta(hours=horas)
        return float(df[df["datahora"] <= corte][col].sum())

    # nº de dias (últimos 5) com chuva "intensa" (>= limiar 24h)
    limiar = config.LIMIARES_CHUVA["acumulado_24h_intensa"]
    dias_intensos = 0
    for i in range(1, 6):
        ini = agora - pd.Timedelta(days=i)
        fim = agora - pd.Timedelta(days=i - 1)
        acc = float(passado[(passado["datahora"] >= ini) & (passado["datahora"] < fim)]
                    ["precipitacao_mm"].sum())
        if acc >= limiar:
            dias_intensos += 1

    return {
        "acumulado_obs_24h_mm": round(soma(passado, 24), 1),
        "acumulado_obs_72h_mm": round(soma(passado, 72), 1),
        "acumulado_obs_7d_mm":  round(soma(passado, 24 * 7), 1),
        "previsto_24h_mm":      round(soma(futuro, 24, passado_flag=False), 1),
        "previsto_48h_mm":      round(soma(futuro, 48, passado_flag=False), 1),
        "previsto_72h_mm":      round(soma(futuro, 72, passado_flag=False), 1),
        "dias_chuva_intensa_5d": dias_intensos,
    }


if __name__ == "__main__":
    dados = coletar_previsao()
    print(dados["resumo"])
    print(dados["diaria"].head())
