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
def gauge_estagio(classificacao: dict, tema: str = "dark") -> go.Figure:
    p = paleta(tema)
    indice = classificacao.get("indice", 0)
    estagio = classificacao.get("estagio", "NORMALIDADE")

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
                "tickfont": {"size": 12, "color": p["txt"]},
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
               "font": {"size": 20, "color": classificacao.get("cor", "#2E9E44")}},
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
                      height=320, margin=dict(l=70, r=70, t=70, b=10))
    return fig


def banner_estagio(classificacao: dict, timestamp: str) -> dbc.Alert:
    cor = classificacao.get("cor", "#2E9E44")
    return dbc.Alert(
        [
            html.H2(f"ESTÁGIO OPERACIONAL: {classificacao.get('estagio', '—')}",
                    className="mb-1 fw-bold"),
            html.Div(f"Última atualização: {timestamp}", className="small opacity-75 mb-2"),
            html.Div([html.Div(j, className="mb-1")
                      for j in classificacao.get("justificativas", [])],
                     className="mb-0"),
        ],
        style={"backgroundColor": cor, "color": "white", "border": "none",
               "borderRadius": "14px"},
        className="shadow",
    )


# ──────────────────────────────────────────────────────────────────────────
# GRÁFICOS DE LINHA
# ──────────────────────────────────────────────────────────────────────────
def grafico_guaiba(serie: list[dict], tema: str = "dark") -> go.Figure:
    p = paleta(tema)
    fig = go.Figure()
    df = pd.DataFrame(serie)
    if not df.empty and "nivel_m" in df:
        df["datahora"] = pd.to_datetime(df["datahora"])
        fig.add_trace(go.Scatter(
            x=df["datahora"], y=df["nivel_m"], mode="lines",
            name="Nível do Guaíba", line=dict(color="#4EA8DE", width=3),
            fill="tozeroy", fillcolor="rgba(78,168,222,0.12)",
            hovertemplate="<b>Guaíba — Cais Mauá</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível: %{y:.2f} m<extra></extra>",
        ))
    for cota, nome, cor in (
        (config.COTA_ATENCAO_GUAIBA, "Cota de Atenção", config.CORES_ESTAGIOS["MOBILIZAÇÃO"]),
        (config.COTA_ALERTA_GUAIBA, "Cota de Alerta", config.CORES_ESTAGIOS["ALERTA"]),
        (config.COTA_INUNDACAO_GUAIBA, "Cota de Inundação",
         config.CORES_ESTAGIOS["SITUAÇÃO DE EMERGÊNCIA"]),
    ):
        fig.add_hline(y=cota, line_dash="dash", line_color=cor,
                      annotation_text=f"{nome} ({cota:.2f} m)",
                      annotation_font_color=cor)
    fig.update_layout(
        title="Nível do Guaíba — Cais Mauá (últimos 7 dias)",
        hoverlabel=p["hover"],
        yaxis_title="metros", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
        xaxis=dict(gridcolor=p["grade"]), yaxis=dict(gridcolor=p["grade"]),
        height=380, margin=dict(l=40, r=20, t=60, b=30),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


def grafico_precipitacao(horaria: list[dict], diaria: list[dict], tema: str = "dark") -> go.Figure:
    p = paleta(tema)
    fig = go.Figure()
    agora = pd.Timestamp.now()

    dfh = pd.DataFrame(horaria)
    if not dfh.empty:
        dfh["datahora"] = pd.to_datetime(dfh["datahora"])
        obs = dfh[dfh["datahora"] <= agora]
        prev = dfh[dfh["datahora"] > agora]
        _hover_chuva = ("<b>{titulo}</b><br>Data: %{{x|%d/%m/%Y}}<br>"
                        "Hora: %{{x|%H:%M}}<br>Chuva: %{{y:.1f}} mm/h"
                        "<extra></extra>")
        fig.add_trace(go.Bar(x=obs["datahora"], y=obs["precipitacao_mm"],
                             name="Observada (mm/h)", marker_color="#4EA8DE",
                             hovertemplate=_hover_chuva.format(titulo="Chuva observada")))
        fig.add_trace(go.Bar(x=prev["datahora"], y=prev["precipitacao_mm"],
                             name="Prevista (mm/h)", marker_color="#9B8CE0",
                             opacity=0.7,
                             hovertemplate=_hover_chuva.format(titulo="Chuva prevista")))
        # linha "agora": add_shape (add_vline com datetime dispara bug no plotly)
        fig.add_shape(type="line", x0=agora, x1=agora, y0=0, y1=1,
                      yref="paper", line=dict(dash="dot", color=p["txt"], width=1))
        fig.add_annotation(x=agora, y=1, yref="paper", text="agora",
                           showarrow=False, yshift=8, font=dict(color=p["txt"], size=11))

    dfd = pd.DataFrame(diaria)
    if not dfd.empty:
        dfd["data"] = pd.to_datetime(dfd["data"])
        fig.add_trace(go.Scatter(
            x=dfd["data"] + pd.Timedelta(hours=12),
            y=dfd["precipitacao_total_mm"],
            name="Total diário (mm)", mode="lines+markers",
            line=dict(color="#F2830B", width=2), yaxis="y2",
            hovertemplate="<b>Total diário</b><br>Data: %{x|%d/%m/%Y}<br>"
                          "Acumulado: %{y:.1f} mm<extra></extra>",
        ))

    fig.update_layout(
        title="Precipitação em Porto Alegre — observada e prevista (Open-Meteo)",
        hoverlabel=p["hover"],
        yaxis=dict(title="mm/h", gridcolor=p["grade"]),
        yaxis2=dict(title="mm/dia", overlaying="y", side="right", showgrid=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color=p["txt"], barmode="overlay", height=380,
        xaxis=dict(gridcolor=p["grade"]),
        margin=dict(l=40, r=50, t=60, b=30),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────
# DATATABLE
# ──────────────────────────────────────────────────────────────────────────
def grafico_afluentes(series: dict, tema: str = "dark") -> go.Figure:
    p = paleta(tema)
    """Níveis dos afluentes (Gravataí, Sinos, Caí, Jacuí) — últimos 7 dias."""
    cores = {"Rio_Gravatai": "#F2B90B", "Rio_dos_Sinos_SaoLeopoldo": "#5FD068",
             "Rio_Cai": "#F2830B", "Rio_Cai_Montenegro": "#E85D24",
             "Rio_Cai_NovaPalmira": "#C98A3D",
             "Rio_Jacui_TriunfoAmarop": "#9B8CE0", "Rio_Jacui_Triunfo": "#9B8CE0"}
    rotulos = {"Rio_Gravatai": "Gravataí", "Rio_dos_Sinos_SaoLeopoldo": "Sinos (S. Leopoldo)",
               "Rio_Cai": "Caí (Barca)", "Rio_Cai_Montenegro": "Caí (Montenegro)",
               "Rio_Cai_NovaPalmira": "Caí (N. Palmira)",
               "Rio_Jacui_TriunfoAmarop": "Jacuí (Triunfo)",
               "Rio_Jacui_Triunfo": "Jacuí (Triunfo)"}
    # Uma cidade de referência por afluente (decisão de produto 25/07)
    principais = ("Rio_Gravatai", "Rio_dos_Sinos_SaoLeopoldo",
                  "Rio_Cai", "Rio_Jacui_Triunfo", "Rio_Jacui_TriunfoAmarop")
    fig = go.Figure()
    for nome, registros in (series or {}).items():
        if nome not in principais:
            continue
        df = pd.DataFrame(registros)
        if df.empty or "nivel_m" not in df:
            continue
        df["datahora"] = pd.to_datetime(df["datahora"])
        df = df.dropna(subset=["nivel_m"])
        rotulo = rotulos.get(nome, nome)
        fig.add_trace(go.Scatter(
            x=df["datahora"], y=df["nivel_m"], mode="lines",
            name=rotulo,
            line=dict(color=cores.get(nome, "#AAAAAA"), width=2.5),
            hovertemplate=f"<b>{rotulo}</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível: %{y:.2f} m<extra></extra>",
        ))
    fig.update_layout(
        title="Afluentes do Guaíba — nível (últimos 7 dias)",
        hoverlabel=p["hover"],
        yaxis_title="metros", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
        xaxis=dict(gridcolor=p["grade"]), yaxis=dict(gridcolor=p["grade"]),
        height=380, margin=dict(l=40, r=20, t=60, b=30),
        legend=dict(orientation="h", y=-0.15),
    )
    return fig


# ──────────────────────────────────────────────────────────────────────────
# CARDS: Nível × Cota de Inundação (Guaíba + afluentes)
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
    p = paleta(tema)
    """Cards centralizados: Nível — Cota de Inundação — Município — Estação."""
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
                html.Div(style={"width": f"{min(pct, 100):.0f}%",
                                "height": "100%", "borderRadius": "4px",
                                "backgroundColor": cor}),
                style={"height": "8px", "borderRadius": "4px",
                       "backgroundColor": p["track"],
                       "overflow": "hidden"},
                className="mb-2")
            rodape = html.Small(f"{pct:.0f}% da cota de inundação",
                                className="text-secondary")
        else:
            corpo_valor = html.H3(
                f"{nivel:.2f} m" if nivel is not None else "—",
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

    tiles = []
    for num in range(1, 18):
        al = capturados.get(num)
        nome = (al or {}).get("regiao_nome") or config.REGIOES_POACLIMA.get(num, f"Região {num}")
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

        tiles.append(dbc.Col(html.Div([
            html.Div(f"{num}", className="fw-bold",
                     style={"fontSize": "0.9rem", "opacity": 0.85}),
            html.Div(nome, className="small fw-bold",
                     style={"lineHeight": "1.1"}),
            html.Div(status, className="small", style={"opacity": 0.9}),
            html.Div(detalhe, className="small",
                     style={"opacity": 0.75, "fontSize": "0.68rem"}) if detalhe else None,
        ], className="text-center text-white p-2 h-100",
            style={"backgroundColor": cor, "borderRadius": "10px",
                   "minHeight": "78px"}),
            xl=2, lg=2, md=3, sm=4, xs=6, className="mb-2",
            style={"minWidth": "150px"}))

    return html.Div([
        html.H6("Risco por região — Defesa Civil (Poaclima)",
                className="text-light text-center mb-1"),
        html.Small("Status capturado dos marcadores do mapa oficial · "
                   "cinza = região sem popup capturado nesta coleta",
                   className="text-secondary d-block text-center mb-2"),
        dbc.Row(tiles, className="g-2 justify-content-center grid-regioes"),
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
