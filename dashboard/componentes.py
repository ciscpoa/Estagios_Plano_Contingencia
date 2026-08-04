# -*- coding: utf-8 -*-
"""
componentes.py
==============
Componentes visuais do dashboard (Plotly + Dash Bootstrap):

* Gauge (velocímetro) de 5 faixas com o ESTÁGIO OPERACIONAL atual
* Banner colorido do estágio + justificativas
* Gráficos de linha: nível do Guaíba (com as 3 cotas) e precipitação
  (observada + prevista)
* DataTable com os dados brutos consolidados
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

import config

FUNDO = "#101418"
GRADE = "rgba(255,255,255,0.08)"
TXT = "#E8ECF1"


def paleta(tema: str = "dark") -> dict:
    """Cores dos gráficos por tema (dark / claro)."""
    if tema == "claro":
        return {"txt": "#1F2733", "grade": "rgba(0,0,0,0.10)",
                "track": "rgba(0,0,0,0.08)",
                "hover": dict(bgcolor="#FFFFFF", bordercolor="#B9C2CC",
                              font=dict(size=13, color="#1F2733"),
                              align="left")}
    return {"txt": TXT, "grade": GRADE, "track": "rgba(255,255,255,0.08)",
            "hover": dict(bgcolor="#1B222B", bordercolor="#3A4552",
                          font=dict(size=13, color="#E8ECF1"), align="left")}


# ──────────────────────────────────────────────────────────────────────────
# GAUGE DO ESTÁGIO
# ──────────────────────────────────────────────────────────────────────────
def gauge_estagio(classificacao: dict, tema: str = "dark",
                  compacto: bool = False) -> go.Figure:
    """
    Velocímetro das 5 faixas do Plano.

    `compacto=True` é a versão que vive no CABEÇALHO, ao lado do logo e do
    título: mesmo desenho, tipos e margens menores. O estágio é a primeira
    informação que um operador procura, então ele sobe para o topo da
    página em vez de ficar no meio dos gráficos.
    """
    p = paleta(tema)
    indice = classificacao.get("indice", 0)

    faixas = [
        {"range": [i, i + 1], "color": config.CORES_ESTAGIOS[e]}
        for i, e in enumerate(config.ESTAGIOS)
    ]
    fig = go.Figure(go.Indicator(
        mode="gauge",
        value=indice + 0.5,
        gauge={
            "axis": {
                "range": [0, 5],
                "tickvals": [0.5, 1.5, 2.5, 3.5, 4.5],
                "ticktext": ["Normalidade", "Mobilização", "Alerta",
                             "Emergência", "Crise"],
                "tickfont": {"size": 10 if compacto else 12, "color": p["txt"]},
            },
            "bar": {"color": "rgba(255,255,255,0.85)", "thickness": 0.22},
            "steps": faixas,
            "threshold": {
                "line": {"color": "white", "width": 4},
                "thickness": 0.9,
                "value": indice + 0.5,
            },
        },
        title={"text": "<b>ESTÁGIO OPERACIONAL</b>",
               "font": {"size": 14 if compacto else 20,
                        "color": classificacao.get("cor", "#2E9E44")}},
    ))
    if compacto:
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
                          height=210, margin=dict(l=42, r=42, t=38, b=4))
    else:
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
                          height=320, margin=dict(l=70, r=70, t=70, b=10))
    return fig


def banner_estagio(classificacao: dict, timestamp: str) -> dbc.Alert:
    cor = classificacao.get("cor", "#2E9E44")
    return dbc.Alert(
        [
            html.H2("ESTÁGIO OPERACIONAL: "
                    + (classificacao.get("rotulo")
                       or classificacao.get("estagio", "—")),
                    className="mb-1 fw-bold"),
            html.Div(f"Última atualização: {timestamp}", className="small opacity-75 mb-2"),
            html.Div([html.Div(j, className="mb-1")
                      for j in classificacao.get("justificativas", [])
                      if not j.lstrip().startswith(("⚑", "⚙"))],
                     className="mb-0"),
        ],
        style={"backgroundColor": cor, "color": "white", "border": "none",
               "borderRadius": "14px"},
        className="shadow",
    )


# ──────────────────────────────────────────────────────────────────────────
# GRÁFICOS DE LINHA
# ──────────────────────────────────────────────────────────────────────────
def grafico_guaiba(serie: list[dict], tema: str = "dark",
                   previsao: list[dict] | None = None) -> go.Figure:
    """
    Nível OBSERVADO do Guaíba + as três cotas de referência.

    O painel não faz previsão hidrológica de nível: a série termina na
    última leitura efetivamente medida no Cais Mauá, marcada pela linha
    vertical "Agora". O parâmetro `previsao` continua na assinatura só
    para não quebrar quem já chama a função (app.py, site_estatico.py,
    relatorio_pdf.py) — ele é ignorado de propósito.
    """
    p = paleta(tema)
    fig = go.Figure()
    df = pd.DataFrame(serie)
    if not df.empty and "nivel_m" in df:
        df["datahora"] = pd.to_datetime(df["datahora"])
        fig.add_trace(go.Scatter(
            x=df["datahora"], y=df["nivel_m"], mode="lines",
            name="Nível observado", line=dict(color="#4EA8DE", width=3),
            fill="tozeroy", fillcolor="rgba(78,168,222,0.12)",
            hovertemplate="<b>Guaíba — Cais Mauá</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível: %{y:.2f} m<extra></extra>",
        ))

        # "Agora" = última observação (não o relógio do navegador); assim a
        # linha também evidencia quando a coleta está atrasada.
        fig.add_vline(
            x=df["datahora"].max().to_pydatetime(),
            line_width=2, line_dash="dot",
            line_color="#FFFFFF" if tema != "claro" else "#334155",
            annotation_text="Agora · última observação",
            annotation_position="top",
            annotation_font_color=p["txt"])

    # Traço e espessura crescentes com a gravidade. Impresso em preto e
    # branco as três cores viram o mesmo cinza; o pontilhado fino, o
    # tracejado e a linha cheia continuam diferentes entre si.
    for cota, nome, cor, traco, largura in (
        (config.COTA_ATENCAO_GUAIBA, "Cota de Atenção",
         config.CORES_ESTAGIOS["MOBILIZAÇÃO"], "dot", 1.6),
        (config.COTA_ALERTA_GUAIBA, "Cota de Alerta",
         config.CORES_ESTAGIOS["ALERTA"], "dash", 2.0),
        (config.COTA_INUNDACAO_GUAIBA, "Cota de Inundação",
         config.CORES_ESTAGIOS["SITUAÇÃO DE EMERGÊNCIA"], "solid", 2.6),
    ):
        fig.add_hline(y=cota, line_dash=traco, line_color=cor,
                      line_width=largura,
                      annotation_text=f"{nome} ({cota:.2f} m)",
                      annotation_font_color=cor)
    fig.update_layout(
        title=("Nível do Guaíba — Cais Mauá · observado"
               "<br><sup>Série termina na última leitura medida "
               "(ANA · Cais Mauá)</sup>"),
        hoverlabel=p["hover"],
        yaxis_title="metros", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
        xaxis=dict(gridcolor=p["grade"]), yaxis=dict(gridcolor=p["grade"]),
        height=380, margin=dict(l=40, r=20, t=60, b=30),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def grafico_precipitacao(horaria: list[dict], diaria: list[dict],
                         tema: str = "dark",
                         obs_inmet: list[dict] | None = None,
                         previsao_poa: list[dict] | None = None,
                         fonte_obs: str = "Open-Meteo",
                         fonte_prev: str = "Open-Meteo",
                         obs_diaria: list[dict] | None = None) -> go.Figure:
    """
    Chuva POR DIA: quanto já choveu e quanto está previsto.

    Antes o gráfico tinha dois eixos Y — mm/h à esquerda, para as barras
    horárias, e mm/dia à direita, para os acumulados. Quem monta o painel lê
    isso sem esforço; quem abre a página uma vez na vida, não: são duas
    escalas, dois zeros e a mesma palavra "chuva" medindo coisas diferentes.
    Ficou só o acumulado diário, num eixo só — que é a pergunta que as
    pessoas realmente fazem: quanto choveu hoje e quanto vem por aí.

    A série horária continua chegando aqui: ela ainda serve de previsão de
    reserva quando não há a previsão oficial. Só não é mais desenhada.

    Medida e previsão convivem no dia de hoje, lado a lado, de propósito: de
    manhã o acumulado observado é parcial, e esconder a previsão do próprio
    dia faria o painel subestimar justamente o dia que importa.
    """
    p = paleta(tema)
    fig = go.Figure()
    agora = pd.Timestamp.now()
    hoje = agora.normalize()

    COR_MEDIDA = "#F2830B"      # o mesmo laranja que já significa "observado"
    COR_PREVISTA = "#C2187E"    # e o mesmo magenta que já significa "previsto"

    def _por_dia(serie) -> pd.DataFrame:
        df = pd.DataFrame(serie or [])
        if df.empty or "precipitacao_total_mm" not in df or "data" not in df:
            return pd.DataFrame()
        df["data"] = pd.to_datetime(df["data"]).dt.normalize()
        df["precipitacao_total_mm"] = pd.to_numeric(
            df["precipitacao_total_mm"], errors="coerce")
        return (df.dropna(subset=["precipitacao_total_mm"])
                  .sort_values("data").reset_index(drop=True))

    # ── Chuva MEDIDA (fonte que venceu a cadeia de observação) ───────
    tem_obs_local = bool(obs_inmet)
    dfo = _por_dia(obs_diaria if obs_diaria else
                   ([] if tem_obs_local else diaria))
    rotulo_obs = fonte_obs if (obs_diaria or tem_obs_local) else "Open-Meteo"
    if not dfo.empty:
        # Nada de pintar dia futuro como medição: a série diária de reserva
        # do Open-Meteo traz previsão junto, e ela não é observação.
        dfo = dfo[dfo["data"] <= hoje]

    # ── Chuva PREVISTA (oficial; horária do Open-Meteo como reserva) ─
    dfp = _por_dia(previsao_poa)
    rotulo_prev = fonte_prev if not dfp.empty else "Open-Meteo"
    if not dfp.empty:
        dfp = dfp[dfp["data"] >= hoje]
    else:
        dfh = pd.DataFrame(horaria or [])
        if not dfh.empty and "precipitacao_mm" in dfh:
            dfh["datahora"] = pd.to_datetime(dfh["datahora"])
            futuro = dfh[dfh["datahora"] > agora]
            if not futuro.empty:
                soma = (futuro.set_index("datahora")["precipitacao_mm"]
                        .astype(float).resample("D").sum())
                dfp = pd.DataFrame({"data": soma.index.normalize(),
                                    "precipitacao_total_mm": soma.values})

    if dfo.empty and dfp.empty:
        fig.add_annotation(text="Sem dados de chuva nesta coleta.",
                           showarrow=False, xref="paper", yref="paper",
                           x=0.5, y=0.5, font=dict(color=p["txt"], size=14))

    # ── Onde cada barra é desenhada ─────────────────────────────────
    # Antes o Plotly agrupava as duas séries e empurrava a medida para a
    # esquerda e a previsão para a direita do dia — mesmo nos dias em que
    # só uma delas existe, que é a esmagadora maioria. O resultado era um
    # painel com todas as barras deslocadas do próprio rótulo.
    #
    # Agora a posição é dada barra a barra: dia com uma série só, barra
    # cheia centrada no dia; dia com as duas (hoje, em que o medido é
    # parcial e a previsão é do dia inteiro), duas meias-barras lado a
    # lado, dividindo o mesmo espaço. As unidades são milissegundos
    # porque o eixo é de datas.
    DIA = 86_400_000.0
    LARG_CHEIA, LARG_MEIA, FOLGA = 0.62 * DIA, 0.30 * DIA, 0.02 * DIA
    dias_divididos = (set(dfo["data"]) & set(dfp["data"])
                      if not dfo.empty and not dfp.empty else set())

    def _geometria(datas, lado: str):
        """Devolve (larguras, deslocamentos) em ms, uma entrada por barra."""
        larguras, deslocs = [], []
        for d in datas:
            if d in dias_divididos:
                larguras.append(LARG_MEIA)
                deslocs.append(-LARG_MEIA - FOLGA / 2 if lado == "esq"
                               else FOLGA / 2)
            else:
                larguras.append(LARG_CHEIA)
                deslocs.append(-LARG_CHEIA / 2)     # centraliza no meio-dia
        return larguras, deslocs

    teto = 0.0
    if not dfo.empty:
        teto = max(teto, float(dfo["precipitacao_total_mm"].max() or 0))
        larg_o, desl_o = _geometria(dfo["data"], "esq")
        fig.add_trace(go.Bar(
            x=dfo["data"] + pd.Timedelta(hours=12),
            y=dfo["precipitacao_total_mm"],
            width=larg_o, offset=desl_o,
            name=f"Chuva medida — {rotulo_obs}",
            marker=dict(color=COR_MEDIDA),
            text=[f"{v:.0f}" for v in dfo["precipitacao_total_mm"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=p["txt"], size=11),
            hovertemplate="<b>Chuva medida</b><br>%{x|%d/%m/%Y}<br>"
                          "%{y:.1f} mm no dia<extra></extra>"))

    if not dfp.empty:
        teto = max(teto, float(dfp["precipitacao_total_mm"].max() or 0))
        descricao = (pd.DataFrame(previsao_poa or []).get("descricao")
                     if previsao_poa else None)
        dados_extra = (descricao.fillna("").tolist()[:len(dfp)]
                       if descricao is not None else [""] * len(dfp))
        larg_p, desl_p = _geometria(dfp["data"], "dir")
        fig.add_trace(go.Bar(
            x=dfp["data"] + pd.Timedelta(hours=12),
            y=dfp["precipitacao_total_mm"],
            width=larg_p, offset=desl_p,
            name=f"Chuva prevista — {rotulo_prev}",
            # Barra hachurada é a convenção de "ainda não aconteceu": a cor
            # separa as duas séries, a textura diz que uma delas é aposta.
            marker=dict(color=COR_PREVISTA, opacity=0.9,
                        pattern=dict(shape="/", size=5, solidity=0.25,
                                     fgcolor="#FFFFFF")),
            text=[f"{v:.0f}" for v in dfp["precipitacao_total_mm"]],
            textposition="outside", cliponaxis=False,
            textfont=dict(color=p["txt"], size=11),
            customdata=dados_extra,
            hovertemplate="<b>Chuva prevista</b><br>%{x|%d/%m/%Y}<br>"
                          "%{customdata}<br>%{y:.0f} mm no dia"
                          "<extra></extra>"))

    # Divisor entre o que foi medido e o que é aposta. Quando hoje tem as
    # duas barras, a linha vai para a divisa entre elas — no relógio real
    # ela atravessaria a barra da previsão pelo meio.
    x_divisor = (hoje + pd.Timedelta(hours=12)) if dias_divididos else agora
    fig.add_shape(type="line", x0=x_divisor, x1=x_divisor, y0=0, y1=1,
                  yref="paper",
                  line=dict(dash="dot", color=p["txt"], width=1))
    fig.add_annotation(x=x_divisor, y=1, yref="paper", text="agora",
                       showarrow=False, yshift=8,
                       font=dict(color=p["txt"], size=11))

    fig.update_layout(
        title=dict(
            text=("Chuva por dia em Porto Alegre<br>"
                  "<span style='font-size:13px;opacity:.72'>quanto já choveu "
                  "e quanto está previsto, em milímetros</span>"),
            x=0.5, xanchor="center", y=0.94, yanchor="top",
            font=dict(size=19)),
        hoverlabel=p["hover"],
        # Com largura e deslocamento definidos barra a barra, o agrupamento
        # automático do Plotly só atrapalharia: 'overlay' respeita o que
        # foi calculado acima.
        barmode="overlay",
        yaxis=dict(title="mm no dia", gridcolor=p["grade"],
                   range=[0, (teto or 1) * 1.22], zeroline=False),
        xaxis=dict(gridcolor=p["grade"], tickformat="%d/%m",
                   dtick=86400000.0, ticklabelmode="period"),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color=p["txt"], height=380,
        margin=dict(l=55, r=25, t=88, b=40),
        legend=dict(orientation="h", y=-0.18),
    )
    return fig


def grafico_afluentes(series: dict, tema: str = "dark") -> go.Figure:
    """
    Afluentes observados + o Guaíba observado no Cais Mauá (eixo direito).

    Somente dado medido: as séries param na linha "Agora" (última leitura
    da ANA). Previsão hidrológica de nível não é atribuição deste painel.
    """
    p = paleta(tema)
    # Uma cor por régua. Sem entrada aqui a linha sai cinza — foi o que
    # aconteceu com o Taquari e com o segundo Jacuí, três traços cinzentos
    # indistinguíveis no mesmo gráfico.
    cores = {"Rio_Gravatai": "#F2B90B", "Rio_dos_Sinos_SaoLeopoldo": "#5FD068",
             "Rio_Cai": "#F2830B", "Rio_Cai_Montenegro": "#E85D24",
             "Rio_Cai_NovaPalmira": "#C98A3D",
             "Rio_Jacui_TriunfoAmarop": "#9B8CE0", "Rio_Jacui_Triunfo": "#9B8CE0",
             "Rio_Jacui_CachoeiraDoSul": "#C6B9F2",
             "Rio_Taquari_Taquari": "#E86FA9", "Rio_Taquari_Mucum": "#F0A8C8"}
    # Cada rio com um traço próprio: fotocopiado em cinza, cinco linhas
    # coloridas viram cinco linhas iguais. O traço sobrevive à cópia.
    tracos = {"Rio_Gravatai": "solid",
              "Rio_dos_Sinos_SaoLeopoldo": "dash",
              "Rio_Cai": "dot", "Rio_Cai_Montenegro": "dot",
              "Rio_Cai_NovaPalmira": "longdash",
              "Rio_Jacui_Triunfo": "dashdot",
              "Rio_Jacui_TriunfoAmarop": "dashdot",
              "Rio_Jacui_CachoeiraDoSul": "longdashdot",
              "Rio_Taquari_Taquari": "longdash",
              "Rio_Taquari_Mucum": "longdashdot"}
    configurados = getattr(config, "AFLUENTES_GUAIBA", {})
    principais = tuple(configurados)
    meta_modelo = (series or {}).get("__meta_alinhamento__", {})
    meta_afluentes = meta_modelo.get("afluentes", {})

    fig = go.Figure()
    for nome, registros in (series or {}).items():
        if nome not in principais:
            continue
        df = pd.DataFrame(registros)
        if df.empty or "nivel_m" not in df:
            continue
        df["datahora"] = pd.to_datetime(df["datahora"])
        df = df.dropna(subset=["nivel_m"])
        cfg = configurados.get(nome, {})
        meta_rio = meta_afluentes.get(nome, {})
        atraso = int(meta_rio.get("tempo_viagem_h",
                                  cfg.get("tempo_viagem_h", 0)))
        tipo_atraso = "físico provisório"
        rotulo = cfg.get("rotulo", nome)
        fig.add_trace(go.Scatter(
            x=df["datahora"], y=df["nivel_m"], mode="lines", name=rotulo,
            line=dict(color=cores.get(nome, "#AAAAAA"), width=2.5,
                      dash=tracos.get(nome, "solid")),
            hovertemplate=f"<b>{rotulo}</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível observado: %{y:.2f} m<br>"
                          f"Tempo de viagem {tipo_atraso}: {atraso} h"
                          "<extra></extra>"))

    guaiba_obs = pd.DataFrame((series or {}).get("__guaiba_observado__", []))
    agora = None
    if not guaiba_obs.empty and {"datahora", "nivel_m"}.issubset(guaiba_obs):
        guaiba_obs["datahora"] = pd.to_datetime(guaiba_obs["datahora"])
        agora = guaiba_obs["datahora"].max()
        fig.add_trace(go.Scatter(
            x=guaiba_obs["datahora"], y=guaiba_obs["nivel_m"],
            mode="lines", name="Guaíba observado (Cais Mauá)",
            yaxis="y2", line=dict(color="#4EA8DE", width=3),
            hovertemplate="<b>Guaíba observado — Cais Mauá</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível: %{y:.2f} m<extra></extra>"))

        # "Agora" é a última leitura efetivamente observada, não o relógio do
        # navegador; assim a linha também evidencia quando a coleta está velha.
        fig.add_vline(
            x=agora.to_pydatetime(), line_width=2, line_dash="dot",
            line_color="#FFFFFF" if tema != "claro" else "#334155",
            annotation_text="Agora · última observação",
            annotation_position="top",
            annotation_font_color=p["txt"])

    # Nada de previsão de nível aqui: a série do Cais Mauá e as dos
    # afluentes terminam na última leitura medida, marcada pela linha
    # vertical "Agora".
    subtitulo = ("Cada régua tem referencial próprio · níveis observados, "
                 "sem previsão")

    fig.update_layout(
        title=("Afluentes do Guaíba e nível observado no Cais Mauá"
               f"<br><sup>{subtitulo}</sup>"),
        hoverlabel=p["hover"],
        yaxis_title="Nível dos afluentes (m)",
        yaxis2=dict(title="Guaíba observado (m)", overlaying="y", side="right",
                    showgrid=False, color="#4EA8DE"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
        xaxis=dict(gridcolor=p["grade"]), yaxis=dict(gridcolor=p["grade"]),
        height=430, margin=dict(l=50, r=60, t=85, b=45),
        legend=dict(orientation="h", y=-0.18))
    return fig


# ──────────────────────────────────────────────────────────────────────────
# AVISOS DO INMET
# ──────────────────────────────────────────────────────────────────────────
def avisos_inmet(av: dict | None, tema: str = "dark"):
    """Retângulo com os avisos meteorológicos vigentes do INMET para POA."""
    av = av or {}
    alertas = av.get("alertas") or []

    if not av.get("consultado", True):
        corpo = html.Div("Não foi possível consultar o INMET nesta "
                         "atualização — verifique em alertas2.inmet.gov.br",
                         className="text-secondary small")
        borda = "#8B95A1"
    elif not alertas:
        corpo = html.Div([html.B("Nenhum aviso meteorológico vigente"),
                          " para Porto Alegre no momento."], className="small")
        borda = config.CORES_ESTAGIOS["NORMALIDADE"]
    else:
        itens = []
        for a in alertas[:4]:
            sev = a.get("severidade") or "Amarelo"
            cor = config.CORES_AVISO_INMET.get(sev, "#E3B505")
            periodo = " · ".join(x for x in (
                f"de {a['inicio']}" if a.get("inicio") else None,
                f"até {a['fim']}" if a.get("fim") else None) if x)
            itens.append(html.Div([
                html.Span(sev, className="badge me-2",
                          style={"backgroundColor": cor, "color": "white"}),
                html.Span((a.get("descricao") or "").strip()[:220],
                          className="small"),
                html.Div(periodo, className="text-secondary",
                         style={"fontSize": "0.78rem"}) if periodo else None,
            ], className="p-2 mb-2 text-start",
                style={"borderLeft": f"6px solid {cor}",
                       "backgroundColor": "rgba(127,127,127,0.08)",
                       "borderRadius": "8px"}))
        corpo = html.Div(itens)
        borda = config.CORES_AVISO_INMET.get(av.get("max_severidade"), "#E3B505")

    titulo = ("Avisos meteorológicos vigentes — INMET"
              + (f" ({len(alertas)})" if alertas else ""))
    return dbc.Card(dbc.CardBody([
        html.H6(titulo, className="text-light text-center mb-2"), corpo,
    ]), className="bg-transparent mb-3",
        style={"border": f"1px solid {borda}", "borderRadius": "12px"})


# ──────────────────────────────────────────────────────────────────────────
# CARDS: Nível × Cota de Inundação
# ──────────────────────────────────────────────────────────────────────────
def _nivel_do_indicador(indicadores: dict, chave: str) -> float | None:
    if chave == "Guaiba_PortoAlegre_CaisMaua":
        return indicadores.get("nivel_guaiba_m")
    if chave == "poaclima_gasometro":
        return indicadores.get("poaclima_gasometro_m")
    if chave == "poaclima_cais_maua":
        return indicadores.get("poaclima_cais_maua_m")
    if chave == "poaclima_riacho_ipiranga":
        return indicadores.get("poaclima_riacho_ipiranga_m")
    dados = (indicadores.get("afluentes") or {}).get(chave) or {}
    v = dados.get("nivel_atual_m")
    return v if v is not None else dados.get("nivel_m")


def cards_rios(indicadores: dict, tema: str = "dark") -> dbc.Row:
    """Cards Nível × Cota de Inundação (cada um com a cota da sua régua)."""
    p = paleta(tema)
    cards = []
    for info in config.INFO_RIOS_CARDS:
        cota = info["cota_inundacao"]
        nivel = _nivel_do_indicador(indicadores or {}, info["chave"])

        if nivel is not None and cota:
            pct = max(0.0, nivel / cota * 100.0)
            if pct >= 100:
                cor = config.CORES_ESTAGIOS["SITUAÇÃO DE EMERGÊNCIA"]
            elif pct >= 85:
                cor = config.CORES_ESTAGIOS["ALERTA"]
            elif pct >= 65:
                cor = config.CORES_ESTAGIOS["MOBILIZAÇÃO"]
            else:
                cor = config.CORES_ESTAGIOS["NORMALIDADE"]
            corpo_valor = html.H3(
                [f"{nivel:.2f} m", html.Span(f" / {cota:.2f} m",
                                             className="fs-6 opacity-75")],
                className="mb-1 fw-bold", style={"color": cor})
            barra = html.Div(
                html.Div(style={"width": f"{min(pct, 100):.0f}%", "height": "100%",
                                "borderRadius": "4px", "backgroundColor": cor}),
                style={"height": "8px", "borderRadius": "4px",
                       "backgroundColor": p["track"], "overflow": "hidden"},
                className="mb-2")
            rodape = html.Small(f"{pct:.0f}% da cota de inundação",
                                className="text-secondary")
        else:
            corpo_valor = html.H3(f"{nivel:.2f} m" if nivel is not None else "—",
                                  className="mb-1 fw-bold text-light")
            barra = html.Div()
            rodape = html.Small("cota de inundação: não informada"
                                if nivel is not None else "sem leitura",
                                className="text-secondary")

        cards.append(dbc.Col(dbc.Card(dbc.CardBody([
            html.H6(info["rotulo"], className="text-light mb-0 fw-bold"),
            html.Small(f"{info['municipio']} · est. {info['estacao']}",
                       className="text-secondary d-block mb-2"),
            corpo_valor, barra, rodape,
        ], className="text-center"),
            className="bg-transparent border-secondary h-100"),
            md=True, xs=6, className="mb-2"))

    return dbc.Row(cards, className="g-3 justify-content-center text-center cards-rios")


def arvore_regras(classificacao: dict, tema: str = "dark") -> html.Div:
    """Árvore E/OU: blocos ativos em destaque, inativos ofuscados."""
    cls = classificacao or {}
    blocos = cls.get("blocos_por_estagio") or {}
    estagio = cls.get("estagio")
    if not blocos or not estagio:
        return html.Div()

    ordem = config.ESTAGIOS
    idx = ordem.index(estagio) if estagio in ordem else 0
    proximo = ordem[idx + 1] if idx + 1 < len(ordem) else None

    def linha(nome, cor_linha, atual):
        bl = blocos.get(nome) or []
        if not bl:
            return None
        nos = []
        for i, b in enumerate(bl):
            estilo = {"flex": "1 1 240px", "maxWidth": "360px",
                      "borderRadius": "10px", "padding": "8px 10px",
                      "border": "1px solid rgba(127,127,127,.4)",
                      "textAlign": "left", "fontSize": "0.84rem"}
            if b["ativo"]:
                estilo |= {"backgroundColor": cor_linha, "color": "white",
                           "fontWeight": "600", "borderColor": cor_linha}
            else:
                estilo |= {"opacity": 0.45}
            # o motivo explica POR QUE o bloco está (ou não) ativo
            motivo = (b.get("motivo") or "").strip()
            conteudo = [html.Div([html.B("✔ " if b["ativo"] else "✖ "),
                                  html.Span(b["titulo"])])]
            if motivo:
                # motivo é multilinha: quebra em <br> preservando os itens "•"
                linhas_motivo = []
                for k, ln in enumerate(motivo.split("\n")):
                    if k:
                        linhas_motivo.append(html.Br())
                    linhas_motivo.append(ln)
                conteudo.append(html.Div(
                    linhas_motivo, style={"fontSize": "0.74rem", "fontWeight": "400",
                                   "lineHeight": "1.35", "opacity": 0.85,
                                   "marginTop": "5px", "paddingTop": "5px",
                                   "borderTop": "1px solid rgba(255,255,255,.22)"}))
            nos.append(html.Div(conteudo, style=estilo, title=motivo))
            if i < len(bl) - 1:
                nos.append(html.Div("E", className="fw-bold text-secondary px-1",
                                    style={"alignSelf": "center"}))
        return dbc.Card(dbc.CardBody([
            html.Div(nome, className="fw-bold", style={"color": cor_linha}),
            html.Small("estágio atual — todos os blocos precisam estar ativos"
                       if atual else
                       "para subir de estágio, faltam os blocos ofuscados",
                       className="text-secondary d-block mb-2"),
            html.Div(nos, className="d-flex flex-wrap justify-content-center gap-2"),
        ]), className="bg-transparent border-secondary mb-2")

    itens = [linha(estagio, cls.get("cor", "#2E9E44"), True)]
    if proximo:
        itens.append(linha(proximo, config.CORES_ESTAGIOS.get(proximo, "#888"), False))
    if any("⚑" in j for j in cls.get("justificativas", [])):
        itens.append(html.Small(
            "⚑ Estágio definido pela regra de piso: um gatilho confirmado em "
            "campo pertence a esta coluna do Plano.",
            className="text-secondary d-block text-center"))

    return html.Div([
        html.H6("Como chegamos a este estágio",
                className="text-light text-center mb-1"),
        html.Small("Regras E/OU do Plano · blocos ativos em destaque",
                   className="text-secondary d-block text-center mb-2"),
        html.Div([i for i in itens if i is not None]),
    ], className="my-3")


def grid_subprefeituras(alertas_regionais: list[dict], tema: str = "dark") -> html.Div:
    """
    Grid das 17 regiões (subprefeituras/OP) com o status de risco da
    Defesa Civil capturado do mapa do Poaclima. Regiões sem popup
    capturado aparecem como "sem dado" (cinza).
    """
    # status capturado por região (se houver mais de um, fica o pior)
    ordem = ["sem risco", "atenção", "alto", "muito alto", "extremo"]

    def _grau(risco: str) -> int:
        r = (risco or "").lower()
        if "extremo" in r:
            return 4
        if "muito alto" in r:
            return 3
        if "alto" in r:
            return 2
        if "atenção" in r or "atencao" in r:
            return 1
        if "sem risco" in r:
            return 0
        return 0

    capturados: dict[int, dict] = {}
    for al in alertas_regionais or []:
        num = al.get("regiao_num")
        if num is None:
            continue
        atual = capturados.get(num)
        if atual is None or _grau(al.get("risco")) > _grau(atual.get("risco")):
            capturados[num] = al

    def _tile(num: int):
        al = capturados.get(num)
        nome = (al or {}).get("regiao_nome") or config.REGIOES_POACLIMA.get(
            num, f"Região {num}")
        if al is None:
            cor = config.CORES_RISCO_POACLIMA["sem dado"]
            status, detalhe = "sem dado", ""
        else:
            g = _grau(al.get("risco"))
            cor = config.CORES_RISCO_POACLIMA.get(ordem[g], "#4A5561")
            status = al.get("risco") or ordem[g]
            partes = [p for p in (al.get("tipo"),
                                  f"até {al.get('fim')}" if al.get("fim") else None) if p]
            detalhe = " · ".join(partes)
        return html.Div([
            html.Div(f"{num}", className="fw-bold",
                     style={"fontSize": "0.9rem", "opacity": 0.85}),
            html.Div(nome, className="small fw-bold", style={"lineHeight": "1.1"}),
            html.Div(status, className="small", style={"opacity": 0.9}),
            html.Div(detalhe, className="small",
                     style={"opacity": 0.75, "fontSize": "0.68rem"}) if detalhe else None,
        ], className="text-center text-white p-2 mx-1 mb-2",
            style={"backgroundColor": cor, "borderRadius": "10px",
                   "minHeight": "78px", "flex": "0 0 11.5%", "minWidth": "120px"})

    # Formato triângulo: 8 em cima, 6 no meio, 3 embaixo
    linhas = [html.Div([_tile(n) for n in faixa],
                       className="d-flex justify-content-center flex-wrap")
              for faixa in (range(1, 9), range(9, 15), range(15, 18))]

    return html.Div([
        html.H6("Risco por região — Defesa Civil (Poaclima)",
                className="text-light text-center mb-1"),
        html.Small("Status capturado dos marcadores do mapa oficial · "
                   "cinza = região sem popup capturado nesta coleta",
                   className="text-secondary d-block text-center mb-2"),
        html.Div(linhas, className="grid-regioes"),
    ])


def tabela_dados(registros: list[dict]) -> dash_table.DataTable:
    # Sanitiza: NaN/None viram "—" (NaN quebra a serialização p/ o navegador)
    import math
    limpos = []
    for reg in registros or []:
        novo = {}
        for k, v in reg.items():
            if v is None or (isinstance(v, float) and math.isnan(v)):
                novo[k] = "—"
            elif isinstance(v, float):
                novo[k] = round(v, 2)
            else:
                novo[k] = v
        limpos.append(novo)
    registros = limpos

    colunas = [
        {"name": "Extração", "id": "datahora_extracao"},
        {"name": "Indicador", "id": "indicador"},
        {"name": "Valor", "id": "valor"},
        {"name": "Unidade", "id": "unidade"},
        {"name": "Fonte", "id": "fonte"},
    ]
    return dash_table.DataTable(
        data=registros, columns=colunas,
        page_size=15, sort_action="native", filter_action="native",
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#1B222B", "color": TXT,
                      "fontWeight": "bold", "border": "none"},
        style_cell={"backgroundColor": FUNDO, "color": TXT,
                    "border": f"1px solid {GRADE}", "padding": "8px",
                    "fontFamily": "Segoe UI, sans-serif", "fontSize": 13,
                    "textAlign": "left"},
        style_data_conditional=[
            {"if": {"filter_query": "{fonte} = 'Plano Contingência'"},
             "color": "#F2B90B"},
        ],
    )
