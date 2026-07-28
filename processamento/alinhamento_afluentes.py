# -*- coding: utf-8 -*-
"""
Alinha níveis dos afluentes pelo tempo de viagem e estima o nível futuro do
Guaíba no Cais Mauá.

A previsão é uma regressão ridge curta e auditável. Ela aprende, na própria
janela coletada, a relação entre a variação de 24 h dos afluentes (já
deslocados até a chegada) e a variação de 24 h do Guaíba. Não é um modelo
hidrodinâmico e deve ser exibida como estimativa experimental.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config

CHAVE_GUAIBA = "Guaiba_PortoAlegre_CaisMaua"
CHAVE_GUAIBA_OBSERVADO = "__guaiba_observado__"
CHAVE_PREVISAO = "__previsao_guaiba__"
CHAVE_META = "__meta_alinhamento__"


def _serie_horaria(df: pd.DataFrame, limite_gap_h: int) -> pd.Series:
    """Converte uma série ANA irregular em mediana horária, sem preencher
    lacunas longas."""
    if df is None or df.empty or not {"datahora", "nivel_m"}.issubset(df.columns):
        return pd.Series(dtype=float)
    dados = df.loc[:, ["datahora", "nivel_m"]].copy()
    dados["datahora"] = pd.to_datetime(dados["datahora"], errors="coerce")
    dados["nivel_m"] = pd.to_numeric(dados["nivel_m"], errors="coerce")
    dados = dados.dropna().drop_duplicates("datahora", keep="last")
    if dados.empty:
        return pd.Series(dtype=float)
    serie = (dados.set_index("datahora")["nivel_m"]
             .sort_index().resample("1h").median())
    return serie.interpolate(method="time", limit=limite_gap_h,
                             limit_area="inside")


def _ridge_prever(x_treino: pd.DataFrame, y_treino: pd.Series,
                  x_futuro: pd.Series) -> tuple[float, float] | None:
    """Ajusta ridge padronizada e retorna (previsão, RMSE do ajuste)."""
    treino = x_treino.copy()
    treino["__y"] = y_treino
    treino = treino.replace([np.inf, -np.inf], np.nan).dropna()
    minimo = int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 48))
    if len(treino) < minimo or x_futuro.isna().any():
        return None

    x = treino.drop(columns="__y").to_numpy(dtype=float)
    y = treino["__y"].to_numpy(dtype=float)
    futuro = x_futuro.to_numpy(dtype=float)

    medias = x.mean(axis=0)
    desvios = x.std(axis=0)
    desvios[desvios < 1e-9] = 1.0
    xz = (x - medias) / desvios
    fz = (futuro - medias) / desvios

    # Intercepto não penalizado; demais coeficientes recebem regularização.
    projeto = np.column_stack([np.ones(len(xz)), xz])
    penalidade = np.eye(projeto.shape[1])
    penalidade[0, 0] = 0.0
    alpha = float(getattr(config, "RIDGE_ALPHA_GUAIBA", 1.0))
    try:
        beta = np.linalg.solve(
            projeto.T @ projeto + alpha * penalidade,
            projeto.T @ y,
        )
    except np.linalg.LinAlgError:
        return None

    ajustado = projeto @ beta
    rmse = float(np.sqrt(np.mean((y - ajustado) ** 2)))
    previsto = float(np.r_[1.0, fz] @ beta)
    return previsto, rmse


def _prever_guaiba(guaiba: pd.Series,
                   alinhadas: dict[str, pd.Series]) -> list[dict]:
    """Prevê até N horas usando apenas sinais a montante já observados."""
    if guaiba.empty or not alinhadas:
        return []

    g = guaiba.dropna()
    if len(g) < int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 48)) + 24:
        return []

    ultimo = g.index.max().floor("h")
    horizonte = int(getattr(config, "HORIZONTE_PREVISAO_GUAIBA_H", 24))
    delta_guaiba_24h = g - g.shift(24)
    resultados: list[dict] = []

    for passo in range(1, horizonte + 1):
        instante = ultimo + pd.Timedelta(hours=passo)
        base_t = instante - pd.Timedelta(hours=24)
        if base_t not in g.index or pd.isna(g.get(base_t)):
            continue

        colunas = {}
        futuro = {}
        for nome, serie in alinhadas.items():
            delta = serie - serie.shift(24)
            valor = delta.get(instante)
            if valor is None or pd.isna(valor):
                continue
            colunas[nome] = delta
            futuro[nome] = float(valor)

        if not colunas:
            continue

        x = pd.DataFrame(colunas)
        ajuste = _ridge_prever(x, delta_guaiba_24h,
                               pd.Series(futuro).reindex(x.columns))
        if ajuste is None:
            continue
        variacao, rmse = ajuste

        # Limites defensivos: evitam extrapolações matemáticas absurdas numa
        # janela curta, sem esconder a incerteza calculada.
        variacao = float(np.clip(variacao, -2.0, 2.0))
        nivel = float(np.clip(float(g.loc[base_t]) + variacao, 0.0, 10.0))
        resultados.append({
            "datahora": instante.isoformat(),
            "nivel_previsto_m": round(nivel, 3),
            "incerteza_m": round(max(rmse, 0.05), 3),
            "afluentes_usados": len(colunas),
        })

    return resultados


def preparar_series_afluentes(rios: dict[str, pd.DataFrame]) -> dict:
    """Retorna o payload já usado por `grafico_afluentes`, acrescido da
    previsão e dos metadados de alinhamento."""
    configurados = getattr(config, "AFLUENTES_GUAIBA", {})
    limite = int(getattr(config, "INTERPOLACAO_MAX_GAP_H", 6))
    payload: dict = {}
    alinhadas: dict[str, pd.Series] = {}
    meta = {"metodo": "ridge_variacao_24h", "experimental": True,
            "afluentes": {}}

    for nome, cfg in configurados.items():
        df = rios.get(nome)
        if df is None or df.empty:
            continue

        # Mantém os registros brutos para as quatro curvas observadas.
        registros = df.loc[:, ["datahora", "nivel_m"]].copy()
        registros["datahora"] = pd.to_datetime(
            registros["datahora"], errors="coerce").astype(str)
        registros["nivel_m"] = pd.to_numeric(
            registros["nivel_m"], errors="coerce")
        registros = registros.dropna()
        payload[nome] = registros.to_dict("records")

        horaria = _serie_horaria(df, limite)
        atraso = int(cfg["tempo_viagem_h"])
        chegada = horaria.copy()
        chegada.index = chegada.index + pd.Timedelta(hours=atraso)
        alinhadas[nome] = chegada
        meta["afluentes"][nome] = {
            "rotulo": cfg.get("rotulo", nome),
            "tempo_viagem_h": atraso,
            "provisorio": bool(cfg.get("provisorio", True)),
        }

    guaiba = _serie_horaria(rios.get(CHAVE_GUAIBA), limite)
    payload[CHAVE_GUAIBA_OBSERVADO] = [
        {"datahora": instante.isoformat(), "nivel_m": round(float(nivel), 3)}
        for instante, nivel in guaiba.dropna().items()
    ]
    previsao = _prever_guaiba(guaiba, alinhadas)
    payload[CHAVE_PREVISAO] = previsao
    meta["horizonte_h"] = int(getattr(config, "HORIZONTE_PREVISAO_GUAIBA_H", 24))
    meta["previsoes_geradas"] = len(previsao)
    payload[CHAVE_META] = meta
    return payload
