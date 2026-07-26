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


def grafico_precipitacao(horaria: list[dict], diaria: list[dict],
                         tema: str = "dark",
                         obs_inmet: list[dict] | None = None,
                         previsao_poa: list[dict] | None = None,
                         fonte_obs: str = "Open-Meteo",
                         fonte_prev: str = "Open-Meteo",
                         obs_diaria: list[dict] | None = None) -> go.Figure:
    """
    Precipitação observada × prevista.

    O Open-Meteo (modelo global) é APENAS reserva: se houver série local
    (Poaclima/INMET/ANA) ou previsão do Poaclima, as séries do Open-Meteo
    nem são desenhadas — para o painel não misturar fontes divergentes.
    """
    p = paleta(tema)
    fig = go.Figure()
    agora = pd.Timestamp.now()

    _hover = ("<b>{titulo}</b><br>Data: %{{x|%d/%m/%Y}}<br>"
              "Hora: %{{x|%H:%M}}<br>Chuva: %{{y:.1f}} mm/h<extra></extra>")

    dfh = pd.DataFrame(horaria)
    if not dfh.empty:
        dfh["datahora"] = pd.to_datetime(dfh["datahora"])

    tem_obs_local = bool(obs_inmet)
    tem_prev_local = bool(previsao_poa)

    # ── Chuva OBSERVADA ──────────────────────────────────────
    if tem_obs_local:
        dfi = pd.DataFrame(obs_inmet)
        dfi["datahora"] = pd.to_datetime(dfi["datahora"])
        fig.add_trace(go.Bar(
            x=dfi["datahora"], y=dfi["precipitacao_mm"],
            name=f"Observada — {fonte_obs} (mm/h)", marker_color="#4EA8DE",
            hovertemplate=_hover.format(titulo=f"Chuva observada · {fonte_obs}")))
    elif not dfh.empty:
        obs = dfh[dfh["datahora"] <= agora]
        fig.add_trace(go.Bar(
            x=obs["datahora"], y=obs["precipitacao_mm"],
            name="Observada — Open-Meteo (mm/h)", marker_color="#4EA8DE",
            hovertemplate=_hover.format(titulo="Chuva observada · Open-Meteo")))

    # ── Chuva PREVISTA horária: só sem a previsão oficial ────
    if not tem_prev_local and not dfh.empty:
        prev = dfh[dfh["datahora"] > agora]
        if not prev.empty:
            fig.add_trace(go.Bar(
                x=prev["datahora"], y=prev["precipitacao_mm"],
                name="Prevista — Open-Meteo (mm/h)", marker_color="#9B8CE0",
                opacity=0.7,
                hovertemplate=_hover.format(titulo="Chuva prevista · Open-Meteo")))

    # linha "agora"
    fig.add_shape(type="line", x0=agora, x1=agora, y0=0, y1=1, yref="paper",
                  line=dict(dash="dot", color=p["txt"], width=1))
    fig.add_annotation(x=agora, y=1, yref="paper", text="agora",
                       showarrow=False, yshift=8,
                       font=dict(color=p["txt"], size=11))

    # ── Total diário observado (da fonte que venceu) ─────────
    dfd = pd.DataFrame(obs_diaria if obs_diaria else
                       ([] if tem_obs_local else diaria))
    if not dfd.empty and "precipitacao_total_mm" in dfd:
        dfd["data"] = pd.to_datetime(dfd["data"])
        rotulo_d = fonte_obs if (obs_diaria or tem_obs_local) else "Open-Meteo"
        fig.add_trace(go.Scatter(
            x=dfd["data"] + pd.Timedelta(hours=12),
            y=dfd["precipitacao_total_mm"],
            name=f"Total diário — {rotulo_d} (mm)", mode="lines+markers",
            line=dict(color="#F2830B", width=2), yaxis="y2",
            hovertemplate="<b>Total diário observado</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>"
                          "Acumulado: %{y:.1f} mm<extra></extra>"))

    # ── Previsão diária oficial (Poaclima/Catavento) ─────────
    if tem_prev_local:
        dfp = pd.DataFrame(previsao_poa)
        dfp["data"] = pd.to_datetime(dfp["data"])
        if "descricao" not in dfp:
            dfp["descricao"] = ""
        fig.add_trace(go.Scatter(
            x=dfp["data"] + pd.Timedelta(hours=12),
            y=dfp["precipitacao_total_mm"],
            name="Previsão diária — Defesa Civil/POA (mm)",
            mode="lines+markers", yaxis="y2",
            line=dict(color="#C2187E", width=2.5, dash="dot"),
            marker=dict(size=9, symbol="diamond"),
            customdata=dfp["descricao"].fillna(""),
            hovertemplate="<b>Previsão · Poaclima/Catavento</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>%{customdata}<br>"
                          "Chuva prevista: %{y:.0f} mm<extra></extra>"))

    fig.update_layout(
        title=(f"Precipitação em Porto Alegre — observada ({fonte_obs}) "
               f"· prevista ({fonte_prev})"),
        hoverlabel=p["hover"],
        barmode="overlay",
        yaxis=dict(title="mm/h", gridcolor=p["grade"]),
        yaxis2=dict(title="mm/dia", overlaying="y", side="right",
                    showgrid=False),
        xaxis=dict(gridcolor=p["grade"]),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color=p["txt"], height=380,
        margin=dict(l=50, r=50, t=60, b=40),
        legend=dict(orientation="h", y=-0.18),
    )
    return fig


def grafico_afluentes(series: dict, tema: str = "dark") -> go.Figure:
    """Níveis dos afluentes — uma cidade de referência por rio."""
    p = paleta(tema)
    cores = {"Rio_Gravatai": "#F2B90B", "Rio_dos_Sinos_SaoLeopoldo": "#5FD068",
             "Rio_Cai": "#F2830B", "Rio_Cai_Montenegro": "#E85D24",
             "Rio_Cai_NovaPalmira": "#C98A3D",
             "Rio_Jacui_TriunfoAmarop": "#9B8CE0", "Rio_Jacui_Triunfo": "#9B8CE0"}
    rotulos = {"Rio_Gravatai": "Gravataí",
               "Rio_dos_Sinos_SaoLeopoldo": "Sinos (S. Leopoldo)",
               "Rio_Cai": "Caí (Barca)", "Rio_Cai_Montenegro": "Caí (Montenegro)",
               "Rio_Cai_NovaPalmira": "Caí (N. Palmira)",
               "Rio_Jacui_TriunfoAmarop": "Jacuí (Rio Pardo)",
               "Rio_Jacui_Triunfo": "Jacuí (Rio Pardo)"}
    # uma cidade por afluente (decisão de produto 25/07)
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
            x=df["datahora"], y=df["nivel_m"], mode="lines", name=rotulo,
            line=dict(color=cores.get(nome, "#AAAAAA"), width=2.5),
            hovertemplate=f"<b>{rotulo}</b><br>"
                          "Data: %{x|%d/%m/%Y}<br>Hora: %{x|%H:%M}<br>"
                          "Nível: %{y:.2f} m<extra></extra>"))

    fig.update_layout(
        title="Afluentes do Guaíba — nível (últimos 7 dias)",
        hoverlabel=p["hover"],
        yaxis_title="metros", paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font_color=p["txt"],
        xaxis=dict(gridcolor=p["grade"]), yaxis=dict(gridcolor=p["grade"]),
        height=380, margin=dict(l=40, r=20, t=60, b=30),
        legend=dict(orientation="h", y=-0.15))
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
