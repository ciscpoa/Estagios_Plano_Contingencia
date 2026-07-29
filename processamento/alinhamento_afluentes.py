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


def _nomes_modelo() -> list[str]:
    return [CHAVE_GUAIBA, *getattr(config, "AFLUENTES_GUAIBA", {}).keys()]


def historico_suficiente() -> bool:
    """True quando o cache contém cobertura mínima para todas as 5 estações."""
    caminho = getattr(config, "HISTORICO_MODELO_GUAIBA_CSV", None)
    if caminho is None or not caminho.exists():
        return False
    try:
        df = pd.read_csv(caminho, usecols=["estacao", "datahora"])
        df["datahora"] = pd.to_datetime(df["datahora"], errors="coerce")
    except Exception:
        return False
    minimo_dias = int(getattr(config, "MIN_DIAS_HISTORICO_MODELO_GUAIBA", 300))
    for nome in _nomes_modelo():
        datas = df.loc[df["estacao"] == nome, "datahora"].dropna()
        if datas.empty or (datas.max() - datas.min()).days < minimo_dias:
            return False
    return True


def atualizar_historico(rios_recentes: dict[str, pd.DataFrame],
                        rios_historicos: dict[str, pd.DataFrame] | None = None
                        ) -> dict[str, pd.DataFrame]:
    """Mescla cache + bootstrap ANA + coleta recente e persiste formato longo."""
    caminho = config.HISTORICO_MODELO_GUAIBA_CSV
    partes = []
    if caminho.exists():
        try:
            partes.append(pd.read_csv(caminho))
        except Exception as exc:
            print(f"[MODELO GUAÍBA] Cache histórico inválido: {exc}")

    for origem in (rios_historicos or {}, rios_recentes or {}):
        for nome in _nomes_modelo():
            df = origem.get(nome)
            if df is None or df.empty or not {"datahora", "nivel_m"}.issubset(df):
                continue
            bloco = df.loc[:, ["datahora", "nivel_m"]].copy()
            bloco.insert(0, "estacao", nome)
            partes.append(bloco)

    if not partes:
        return {}

    longo = pd.concat(partes, ignore_index=True)
    longo["datahora"] = pd.to_datetime(longo["datahora"], errors="coerce")
    longo["nivel_m"] = pd.to_numeric(longo["nivel_m"], errors="coerce")
    longo = (longo.dropna()
             .drop_duplicates(["estacao", "datahora"], keep="last")
             .sort_values(["estacao", "datahora"]))
    corte = longo["datahora"].max() - pd.Timedelta(
        days=int(getattr(config, "DIAS_HISTORICO_MODELO_GUAIBA", 365)) + 7)
    longo = longo[longo["datahora"] >= corte]
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(".tmp")
    longo.to_csv(temporario, index=False)
    temporario.replace(caminho)

    return {
        nome: grupo.loc[:, ["datahora", "nivel_m"]].reset_index(drop=True)
        for nome, grupo in longo.groupby("estacao")
    }


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


def _calibrar_lags(guaiba: pd.Series,
                   afluentes: dict[str, pd.Series]) -> tuple[dict[str, int], dict]:
    """Escolhe o atraso de cada rio pela correlação das variações de 24 h.

    Somente os 70% iniciais são usados na escolha; o trecho final permanece
    cronologicamente posterior e não influencia os atrasos.
    """
    configurados = getattr(config, "AFLUENTES_GUAIBA", {})
    lags, diagnostico = {}, {}
    delta_g = guaiba - guaiba.shift(24)
    corte = delta_g.index.min() + (delta_g.index.max() - delta_g.index.min()) * 0.70
    alvo = delta_g.loc[:corte]

    for nome, serie in afluentes.items():
        cfg = configurados[nome]
        inicio, fim = cfg.get("faixa_lag_h", (cfg["tempo_viagem_h"],
                                                cfg["tempo_viagem_h"]))
        delta_rio = serie - serie.shift(24)
        melhor_lag = int(cfg["tempo_viagem_h"])
        melhor_corr = -np.inf
        melhor_n = 0
        for lag in range(int(inicio), int(fim) + 1):
            chegada = delta_rio.copy()
            chegada.index = chegada.index + pd.Timedelta(hours=lag)
            pares = pd.concat([alvo.rename("g"), chegada.rename("r")],
                              axis=1, join="inner").dropna()
            if len(pares) < 500:
                continue
            corr = pares["g"].corr(pares["r"])
            if pd.notna(corr) and corr > melhor_corr:
                melhor_lag, melhor_corr, melhor_n = lag, float(corr), len(pares)
        lags[nome] = melhor_lag
        diagnostico[nome] = {
            "lag_aprendido_h": melhor_lag,
            "correlacao_variacao_24h": (
                round(melhor_corr, 3) if np.isfinite(melhor_corr) else None),
            "pares_calibracao": melhor_n,
        }
    return lags, diagnostico


def _validar_24h(g: pd.Series,
                 alinhadas: dict[str, pd.Series]) -> dict:
    """Validação cronológica: 85% iniciais treinam, 15% finais testam."""
    passo = 24
    x = pd.DataFrame({
        "guaiba_nivel": g,
        "guaiba_delta_6h": g - g.shift(6),
        "guaiba_delta_24h": g - g.shift(24),
    })
    ultimo = g.last_valid_index()
    if ultimo is None:
        return {"ok": False, "motivo": "sem Guaíba observado"}

    for nome, serie in alinhadas.items():
        nivel = serie.shift(-passo)
        delta = (serie - serie.shift(24)).shift(-passo)
        # Inclui somente o afluente que estará conhecido numa previsão real
        # de 24 h feita no final da série.
        if pd.notna(nivel.get(ultimo)) and pd.notna(delta.get(ultimo)):
            x[f"{nome}_nivel_chegada"] = nivel
            x[f"{nome}_delta_24h_chegada"] = delta

    y = g.shift(-passo).rename("__y")
    dados = pd.concat([x, y], axis=1).replace(
        [np.inf, -np.inf], np.nan).dropna(subset=["__y"])
    minimo = int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 1000))
    if len(dados) < minimo:
        return {"ok": False, "motivo": "histórico insuficiente",
                "amostras": len(dados)}

    corte = max(int(len(dados) * 0.85), minimo)
    treino, teste = dados.iloc[:corte], dados.iloc[corte:]
    if len(teste) < 100:
        return {"ok": False, "motivo": "período de teste insuficiente",
                "amostras_teste": len(teste)}

    colunas = [c for c in x.columns if treino[c].notna().any()]
    medianas = treino[colunas].median()
    xt = treino[colunas].fillna(medianas).to_numpy(float)
    xv = teste[colunas].fillna(medianas).to_numpy(float)
    yt = treino["__y"].to_numpy(float)
    yv = teste["__y"].to_numpy(float)
    medias, desvios = xt.mean(axis=0), xt.std(axis=0)
    desvios[desvios < 1e-9] = 1.0
    xt = (xt - medias) / desvios
    xv = (xv - medias) / desvios
    projeto = np.column_stack([np.ones(len(xt)), xt])
    projeto_v = np.column_stack([np.ones(len(xv)), xv])
    penalidade = np.eye(projeto.shape[1])
    penalidade[0, 0] = 0.0
    alpha = float(getattr(config, "RIDGE_ALPHA_GUAIBA", 1.0))
    try:
        beta = np.linalg.solve(
            projeto.T @ projeto + alpha * penalidade, projeto.T @ yt)
    except np.linalg.LinAlgError:
        return {"ok": False, "motivo": "matriz singular"}

    previsto = projeto_v @ beta
    mae = float(np.mean(np.abs(yv - previsto)))
    rmse = float(np.sqrt(np.mean((yv - previsto) ** 2)))
    persistencia = teste["guaiba_nivel"].to_numpy(float)
    mae_persistencia = float(np.mean(np.abs(yv - persistencia)))
    return {
        "ok": True,
        "horizonte_h": passo,
        "amostras_treino": len(treino),
        "amostras_teste": len(teste),
        "mae_m": round(mae, 3),
        "rmse_m": round(rmse, 3),
        "mae_persistencia_m": round(mae_persistencia, 3),
        "melhor_que_persistencia": mae < mae_persistencia,
    }


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

    g = guaiba
    if g.notna().sum() < int(getattr(config, "MIN_AMOSTRAS_MODELO_GUAIBA", 48)) + 24:
        return []

    ultimo = g.last_valid_index()
    if ultimo is None:
        return []
    ultimo = ultimo.floor("h")
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


def preparar_series_afluentes(rios: dict[str, pd.DataFrame],
                              historico: dict[str, pd.DataFrame] | None = None
                              ) -> dict:
    """Retorna o payload já usado por `grafico_afluentes`, acrescido da
    previsão e dos metadados de alinhamento."""
    configurados = getattr(config, "AFLUENTES_GUAIBA", {})
    limite = int(getattr(config, "INTERPOLACAO_MAX_GAP_H", 6))
    payload: dict = {}
    base_modelo = historico or rios
    horarias_modelo: dict[str, pd.Series] = {}
    alinhadas: dict[str, pd.Series] = {}
    meta = {"metodo": "ridge_lags_aprendidos_1_ano", "experimental": True,
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

        df_modelo = base_modelo.get(nome, df)
        horaria = _serie_horaria(df_modelo, limite)
        horarias_modelo[nome] = horaria

    guaiba = _serie_horaria(base_modelo.get(CHAVE_GUAIBA), limite)
    lags, diagnostico_lags = _calibrar_lags(guaiba, horarias_modelo)
    for nome, horaria in horarias_modelo.items():
        cfg = configurados[nome]
        atraso = int(lags[nome])
        chegada = horaria.copy()
        chegada.index = chegada.index + pd.Timedelta(hours=atraso)
        alinhadas[nome] = chegada
        meta["afluentes"][nome] = {
            "rotulo": cfg.get("rotulo", nome),
            "tempo_viagem_h": atraso,
            "provisorio": diagnostico_lags[nome]["pares_calibracao"] == 0,
            **diagnostico_lags[nome],
        }

    guaiba_recente = _serie_horaria(rios.get(CHAVE_GUAIBA), limite)
    payload[CHAVE_GUAIBA_OBSERVADO] = [
        {"datahora": instante.isoformat(), "nivel_m": round(float(nivel), 3)}
        for instante, nivel in guaiba_recente.dropna().items()
    ]
    previsao = _prever_guaiba(guaiba, alinhadas)
    payload[CHAVE_PREVISAO] = previsao
    meta["horizonte_h"] = int(getattr(config, "HORIZONTE_PREVISAO_GUAIBA_H", 24))
    meta["previsoes_geradas"] = len(previsao)
    meta["validacao_24h"] = _validar_24h(guaiba, alinhadas)
    payload[CHAVE_META] = meta
    return payload
