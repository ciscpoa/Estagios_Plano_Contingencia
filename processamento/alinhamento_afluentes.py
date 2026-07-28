# -*- coding: utf-8 -*-
"""
Alinha níveis dos afluentes pelo tempo de viagem e estima o nível futuro do
Guaíba no Cais Mauá.

A previsão usa uma regressão ridge direta para cada hora do horizonte. Ela
aprende, na própria janela coletada, como o Guaíba respondeu ao seu nível e
tendências recentes e aos quatro afluentes já deslocados até a chegada. Não é
um modelo hidrodinâmico e deve ser exibida como estimativa experimental.
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
    x = x_treino.replace([np.inf, -np.inf], np.nan).copy()
    y = y_treino.replace([np.inf, -np.inf], np.nan)
    linhas_validas = y.notna()
    x = x.loc[linhas_validas]
    y = y.loc[linhas_validas]
    minimo = int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 48))
    if len(y) < minimo or x_futuro.isna().any():
        return None

    # Falhas intermitentes antigas não devem apagar toda a amostra. A mediana
    # é usada somente no treino; a previsão atual nunca inventa sensor futuro.
    medianas = x.median()
    colunas_validas = medianas[medianas.notna()].index
    if len(colunas_validas) == 0:
        return None
    x = x.loc[:, colunas_validas].fillna(medianas[colunas_validas])
    futuro_s = x_futuro.reindex(colunas_validas)
    if futuro_s.isna().any():
        return None

    x = x.to_numpy(dtype=float)
    y = y.to_numpy(dtype=float)
    futuro = futuro_s.to_numpy(dtype=float)

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
    """Prevê cada hora diretamente, sem usar água ainda não observada.

    Para o horizonte h, o modelo histórico relaciona Guaíba(t+h) a:
      * Guaíba(t), variação em 6 h e variação em 24 h;
      * nível e variação em 24 h de cada afluente que chegará em t+h.

    Assim o modelo aprende como o resultado (Guaíba) respondeu anteriormente
    aos mesmos sinais, em vez de apenas transladar visualmente as curvas.
    """
    if guaiba.empty or not alinhadas:
        return []

    g = guaiba.dropna()
    if len(g) < int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 48)) + 24:
        return []

    ultimo = g.index.max().floor("h")
    horizonte = int(getattr(config, "HORIZONTE_PREVISAO_GUAIBA_H", 24))
    nivel_atual = float(g.loc[ultimo])
    resultados: list[dict] = [{
        "datahora": ultimo.isoformat(),
        "nivel_previsto_m": round(nivel_atual, 3),
        "incerteza_m": 0.0,
        "afluentes_usados": 0,
        "ancora_observada": True,
    }]
    anterior = nivel_atual

    for passo in range(1, horizonte + 1):
        instante = ultimo + pd.Timedelta(hours=passo)
        x = pd.DataFrame({
            "guaiba_nivel": g,
            "guaiba_delta_6h": g - g.shift(6),
            "guaiba_delta_24h": g - g.shift(24),
        })
        afluentes_usados = 0

        for nome, serie in alinhadas.items():
            # `serie` já está no horário estimado de chegada. shift(-passo)
            # coloca, na linha t, o sinal que chegará no alvo t+passo.
            chegada_nivel = serie.shift(-passo)
            chegada_delta = (serie - serie.shift(24)).shift(-passo)
            valor_nivel = chegada_nivel.get(ultimo)
            valor_delta = chegada_delta.get(ultimo)
            if (valor_nivel is None or pd.isna(valor_nivel)
                    or valor_delta is None or pd.isna(valor_delta)):
                continue
            x[f"{nome}_nivel_chegada"] = chegada_nivel
            x[f"{nome}_delta_24h_chegada"] = chegada_delta
            afluentes_usados += 1

        # O alvo histórico é o nível observado h horas depois.
        y = g.shift(-passo)
        if ultimo not in x.index:
            break
        # Usa somente variáveis realmente conhecidas na última observação.
        futuro = x.loc[ultimo].dropna()
        x = x.loc[:, futuro.index]
        ajuste = _ridge_prever(x, y, futuro)
        if ajuste is None:
            continue
        nivel_modelo, rmse = ajuste

        # Suaviza diferenças entre os 24 modelos diretos e limita extrapolação
        # muito distante do último nível observado numa janela histórica curta.
        nivel = 0.70 * float(nivel_modelo) + 0.30 * anterior
        nivel = float(np.clip(nivel, nivel_atual - 2.0, nivel_atual + 2.0))
        nivel = float(np.clip(nivel, 0.0, 10.0))
        anterior = nivel
        resultados.append({
            "datahora": instante.isoformat(),
            "nivel_previsto_m": round(nivel, 3),
            "incerteza_m": round(max(rmse, 0.03), 3),
            "afluentes_usados": afluentes_usados,
            "ancora_observada": False,
        })

    return resultados


def preparar_series_afluentes(rios: dict[str, pd.DataFrame]) -> dict:
    """Retorna o payload já usado por `grafico_afluentes`, acrescido da
    previsão e dos metadados de alinhamento."""
    configurados = getattr(config, "AFLUENTES_GUAIBA", {})
    limite = int(getattr(config, "INTERPOLACAO_MAX_GAP_H", 6))
    payload: dict = {}
    alinhadas: dict[str, pd.Series] = {}
    meta = {"metodo": "ridge_direta_por_horizonte", "experimental": True,
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
