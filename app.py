# -*- coding: utf-8 -*-
"""
app.py
======
TAREFA 4 — Dashboard interativo (Dash + dash-bootstrap-components).

Como rodar:
  * VSCode/local :  python app.py            → http://127.0.0.1:8050
  * Google Colab :  from app import rodar_no_colab; rodar_no_colab()
  * Render       :  gunicorn app:server      (o objeto `server` já é exposto)

O dashboard lê `dados/ultimo_snapshot.json` (gerado pelo main_pipeline).
O botão "Atualizar dados agora" reexecuta o pipeline; o Interval
recarrega o snapshot do disco a cada 5 minutos.
"""

from __future__ import annotations

import json

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html, no_update

import config
from dashboard import componentes
from logica.estagios import InputsInfraestrutura

# ──────────────────────────────────────────────────────────────────────────
# APP  (server exposto p/ gunicorn no Render)
# ──────────────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY, dbc.icons.BOOTSTRAP],
    title="Estágios Operacionais — Porto Alegre",
    suppress_callback_exceptions=True,
)
server = app.server  # ← Render/gunicorn

# CSS do modo claro + regras de impressão (Exportar PDF usa window.print)
app.index_string = """<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
#raiz{transition:background-color .3s ease}
.tema-claro{color:#1F2733}
.tema-claro .text-light{color:#1F2733 !important}
.tema-claro .text-secondary{color:#5A6472 !important}
.tema-claro .card{background-color:#FFFFFF !important;border-color:#D9DEE5 !important}
.tema-claro .form-check-label{color:#1F2733 !important}
.tema-claro .btn-outline-info{color:#0B7285;border-color:#0B7285}
@page{size:A4 landscape;margin:10mm}
@media(min-width:1200px){.cards-rios>div{flex:0 0 20%;max-width:20%}}
@media print{
  *{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important}
  .no-print{display:none !important}
  body{background:#FFFFFF !important}
  #raiz{background-color:#FFFFFF !important;max-width:100% !important;padding:0 !important}
  .card,.alert{break-inside:avoid !important;page-break-inside:avoid !important}
  .card{border-color:#CCD2D9 !important;margin-bottom:6px !important}
  .cards-rios>div{flex:0 0 20% !important;max-width:20% !important;min-width:0 !important}
  .grid-regioes>div{flex:0 0 16.66% !important;max-width:16.66% !important;min-width:0 !important}
  .js-plotly-plot,.js-plotly-plot .svg-container{width:100% !important}
  h2{font-size:1.6rem !important}
  h3{font-size:1.3rem !important}
}
</style></head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""


def _ler_snapshot() -> dict | None:
    """
    Lê o snapshot do disco. Se SNAPSHOT_URL estiver definida, busca de lá
    (ex.: JSON gerado pelo GitHub Actions e servido pelo raw.githubusercontent):
    assim o painel roda em hospedagem pequena, sem coletar nada.
    """
    import os

    url = os.environ.get("SNAPSHOT_URL", "").strip()
    if url:
        try:
            import requests
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            print(f"[DASH] Falha ao buscar SNAPSHOT_URL ({exc}); "
                  "tentando o arquivo local.")

    caminho = config.DADOS_DIR / "ultimo_snapshot.json"
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────
# LAYOUT
# ──────────────────────────────────────────────────────────────────────────

app.layout = dbc.Container(id="raiz", fluid=False,
    className="py-4 text-center", style={
    "backgroundColor": "#101418", "minHeight": "100vh", "maxWidth": "1320px"}, children=[

    dcc.Interval(id="intervalo", interval=5 * 60 * 1000),  # 5 min
    dcc.Store(id="store-snapshot"),
    dcc.Store(id="store-tema", storage_type="local", data="dark"),
    dcc.Download(id="download-pdf"),

    # Cabeçalho — tudo centralizado
    html.H3("Plano de Contingência — Estágios Operacionais",
            className="mb-1 fw-bold text-light text-center"),
    html.Div("Porto Alegre/RS · SMS/PMPA · monitoramento automatizado "
             "(ANA · Open-Meteo · INMET · Poaclima)",
             className="text-secondary text-center mb-3"),
    html.Div([
        dbc.Button([html.I(className="bi bi-arrow-clockwise me-2"),
                    "Atualizar dados agora"],
                   id="btn-atualizar", color="info", outline=True),
        dbc.Button([html.I(className="bi bi-sun me-2"), "Modo claro"],
                   id="btn-tema", color="secondary", outline=True),
        dbc.Button([html.I(className="bi bi-filetype-pdf me-2"), "Exportar PDF"],
                   id="btn-pdf", color="danger", outline=True,
                   title=""),
    ], className="mb-3 no-print d-flex justify-content-center gap-2 flex-wrap"),

    html.Div(id="area-fontes", className="text-center"),

    html.Div(id="area-banner", className="text-center"),

    html.Div(id="area-avisos-inmet", className="my-2"),

    # Cards: Nível × Cota de Inundação por rio (ponto 6)
    html.Div(id="area-cards", className="my-3"),

    # Grid das 17 subprefeituras/regiões (risco Defesa Civil / Poaclima)
    html.Div(id="area-regioes", className="my-3"),

    html.Div(id="area-arvore"),

    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="graf-gauge",
                                                config={"displayModeBar": False})),
                         className="bg-transparent border-secondary"), md=5),
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Gatilhos de campo confirmados (SMS/Defesa Civil/CISC)",
                    className="text-light mb-2"),
            html.Div(id="area-gatilhos"),
        ], className="text-center"),
            className="bg-transparent border-secondary"), md=7),
    ], className="g-3 my-1 justify-content-center"),

    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="graf-guaiba")),
                         className="bg-transparent border-secondary"), md=6),
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="graf-afluentes")),
                         className="bg-transparent border-secondary"), md=6),
    ], className="g-3 my-1 justify-content-center"),

    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody(dcc.Graph(id="graf-chuva")),
                         className="bg-transparent border-secondary"), md=10),
    ], className="g-3 my-1 justify-content-center"),

    html.Div("Realizado por: CISC Porto Alegre — Centro de Informações "
             "em Saúde e Clima", className="text-light fw-bold mt-3 mb-1"),
    html.Footer(html.Small(
        "Cotas de referência do Guaíba no Cais Mauá: atenção "
        f"{config.COTA_ATENCAO_GUAIBA} m · alerta {config.COTA_ALERTA_GUAIBA} m · "
        f"inundação {config.COTA_INUNDACAO_GUAIBA} m (Poaclima/Defesa Civil de "
        "Porto Alegre). Cada régua tem referência própria — leituras de "
        "estações diferentes não são comparáveis entre si. "
        "Ferramenta de apoio à decisão — não substitui os canais oficiais "
        "da Defesa Civil.", className="text-secondary"), className="text-center"),
])


# ──────────────────────────────────────────────────────────────────────────
# CALLBACKS
# ──────────────────────────────────────────────────────────────────────────
@app.callback(
    Output("store-snapshot", "data"),
    Input("intervalo", "n_intervals"),
    Input("btn-atualizar", "n_clicks"),
    prevent_initial_call=False,
)
def atualizar_snapshot(_n_int, _n_btn):
    """Carga inicial/Interval: lê do disco. Botão: reexecuta o pipeline
    (que relê o gatilhos_manuais.txt automaticamente)."""
    if dash.ctx.triggered_id == "btn-atualizar":
        from main_pipeline import executar_pipeline
        try:
            return executar_pipeline(usar_selenium=True)
        except Exception as exc:
            print(f"[DASH] Pipeline falhou: {exc}")
    snap = _ler_snapshot()
    return snap if snap else no_update


@app.callback(
    Output("area-fontes", "children"),
    Output("area-banner", "children"),
    Output("area-avisos-inmet", "children"),
    Output("area-cards", "children"),
    Output("area-regioes", "children"),
    Output("area-arvore", "children"),
    Output("area-gatilhos", "children"),
    Output("graf-gauge", "figure"),
    Output("graf-guaiba", "figure"),
    Output("graf-afluentes", "figure"),
    Output("graf-chuva", "figure"),
    Input("store-snapshot", "data"),
    Input("store-tema", "data"),
)
def renderizar(snapshot, tema):
    tema = tema or "dark"
    if not snapshot:
        aviso = dbc.Alert(
            "Nenhum snapshot encontrado. Rode `python main_pipeline.py` "
            "ou clique em “Atualizar dados agora”.",
            color="secondary")
        vazio = componentes.gauge_estagio({"indice": 0, "estagio": "—"}, tema)
        return (html.Div(), aviso, html.Div(), html.Div(), html.Div(),
                html.Div(), html.Div(), vazio,
                componentes.grafico_guaiba([], tema),
                componentes.grafico_afluentes({}, tema),
                componentes.grafico_precipitacao([], [], tema))

    import traceback

    def _seguro(nome, construtor, reserva):
        try:
            return construtor()
        except Exception:
            print(f"[DASH] Falha ao montar '{nome}':")
            traceback.print_exc()
            return reserva

    cls = snapshot.get("classificacao", {})
    ind = snapshot.get("indicadores", {})

    ts_txt = snapshot.get("timestamp", "—")
    if snapshot.get("reclass_info"):
        ts_txt = f"{ts_txt} · {snapshot['reclass_info']}"
    banner = _seguro("banner",
                     lambda: componentes.banner_estagio(cls, ts_txt),
                     dbc.Alert("Falha ao montar o banner (ver log).", color="warning"))
    av_inmet = _seguro("avisos_inmet",
                       lambda: componentes.avisos_inmet(
                           snapshot.get("avisos_inmet"), tema), html.Div())
    cards = _seguro("cards_rios",
                    lambda: componentes.cards_rios(ind, tema), html.Div())
    arvore = _seguro("arvore_regras",
                     lambda: componentes.arvore_regras(cls, tema), html.Div())
    fontes = snapshot.get("fontes") or {}
    indisponiveis = [n for n, ok in fontes.items() if not ok]
    if indisponiveis:
        aviso_fontes = dbc.Alert(
            [html.B("Atenção: "),
             f"nesta coleta não foi possível consultar {', '.join(indisponiveis)}. ",
             "A classificação usa apenas as fontes disponíveis e pode estar "
             "subestimada — consulte os canais oficiais da Defesa Civil."],
            color="warning", className="py-2 small mb-2")
    else:
        aviso_fontes = html.Div()

    ativos = snapshot.get("gatilhos_ativos") or []
    if ativos:
        cor_estagio = cls.get("cor", "#F2830B")
        gat = html.Div([html.Span(a, className="badge fs-6 fw-bold m-1 px-3 py-2",
                                  style={"backgroundColor": cor_estagio,
                                         "color": "white",
                                         "borderRadius": "10px"})
                        for a in ativos])
    else:
        gat = html.Div()  # em branco quando não há gatilhos
    regioes = _seguro("grid_subprefeituras",
                      lambda: componentes.grid_subprefeituras(
                          ind.get("alertas_regionais") or [], tema),
                      html.Div())
    gauge = _seguro("gauge",
                    lambda: componentes.gauge_estagio(cls, tema),
                    componentes.gauge_estagio({"indice": 0, "estagio": "—"}, tema))
    g_guaiba = _seguro("grafico_guaiba",
                       lambda: componentes.grafico_guaiba(snapshot.get("serie_guaiba", []), tema),
                       componentes.grafico_guaiba([], tema))
    g_afl = _seguro("grafico_afluentes",
                    lambda: componentes.grafico_afluentes(
                        snapshot.get("series_afluentes", {}), tema),
                    componentes.grafico_afluentes({}, tema))
    g_chuva = _seguro("grafico_precipitacao",
                      lambda: componentes.grafico_precipitacao(
                          snapshot.get("serie_precipitacao_horaria", []),
                          snapshot.get("serie_precipitacao_diaria", []), tema,
                          obs_inmet=snapshot.get("chuva_obs_inmet"),
                          previsao_poa=snapshot.get("previsao_poaclima"),
                          fonte_obs=snapshot.get("fonte_chuva_obs", "Open-Meteo"),
                          fonte_prev=snapshot.get("fonte_chuva_prev", "Open-Meteo"),
                          obs_diaria=snapshot.get("serie_obs_diaria")),
                      componentes.grafico_precipitacao([], [], tema))
    return (aviso_fontes, banner, av_inmet, cards, regioes, arvore, gat,
            gauge, g_guaiba, g_afl, g_chuva)


@app.callback(
    Output("store-tema", "data"),
    Output("btn-tema", "children"),
    Input("btn-tema", "n_clicks"),
    State("store-tema", "data"),
    prevent_initial_call=False,
)
def alternar_tema(_n, atual):
    """Alterna dark ↔ claro (a escolha fica salva no navegador)."""
    tema = atual or "dark"
    if dash.ctx.triggered_id == "btn-tema":
        tema = "claro" if tema == "dark" else "dark"
    rotulo = ([html.I(className="bi bi-sun me-2"), "Modo claro"]
              if tema == "dark"
              else [html.I(className="bi bi-moon-stars me-2"), "Modo escuro"])
    return tema, rotulo


@app.callback(
    Output("raiz", "className"),
    Output("raiz", "style"),
    Input("store-tema", "data"),
)
def aplicar_tema(tema):
    base = "py-4 text-center"
    estilo = {"minHeight": "100vh", "maxWidth": "1320px",
              "backgroundColor": "#F2F4F7" if tema == "claro" else "#101418"}
    return (base + " tema-claro", estilo) if tema == "claro" else (base, estilo)


@app.callback(
    Output("download-pdf", "data"),
    Input("btn-pdf", "n_clicks"),
    prevent_initial_call=True,
)
def exportar_pdf(_n):
    """Gera o relatório PDF NO SERVIDOR (paisagem, layout controlado)
    a partir do último snapshot e envia para download."""
    snap = _ler_snapshot()
    if not snap:
        print("[PDF] Sem snapshot — rode o pipeline antes de exportar.")
        return no_update
    try:
        from dashboard.relatorio_pdf import gerar_relatorio_pdf
        caminho = gerar_relatorio_pdf(snap)
        return dcc.send_file(caminho)
    except Exception as exc:
        import traceback
        print(f"[PDF] Falha na geração: {exc}")
        traceback.print_exc()
        return no_update


# ──────────────────────────────────────────────────────────────────────────
# SERVIDOR: health check + agendador embutido (Render)
# ──────────────────────────────────────────────────────────────────────────
@server.route("/health")
def _health():
    """Health check do Render — responde mesmo antes do 1º snapshot."""
    existe = (config.DADOS_DIR / "ultimo_snapshot.json").exists()
    return ({"status": "ok", "snapshot": existe}, 200)


@server.route("/diagnostico")
def _diagnostico():
    """Status técnico da última coleta (útil logo após o deploy no Render)."""
    import os as _os

    snap = _ler_snapshot() or {}
    return ({
        "ultima_coleta": snap.get("timestamp"),
        "estagio": (snap.get("classificacao") or {}).get("estagio"),
        "fontes": snap.get("fontes", {}),
        "gatilhos_ativos": snap.get("gatilhos_ativos", []),
        "alertas_regionais": len(((snap.get("indicadores") or {})
                                  .get("alertas_regionais")) or []),
        "ambiente": {
            "render": config.IN_RENDER,
            "selenium_ligado": config.USAR_SELENIUM,
            "chrome_bin": _os.environ.get("CHROME_BIN"),
            "agendador_min": config.INTERVALO_COLETA_MIN,
            "credenciais_ana": bool(_os.environ.get("ANA_IDENTIFICADOR")),
        },
    }, 200)


def _ciclo_agendador():
    """Roda o pipeline no boot e depois a cada INTERVALO_COLETA_MIN minutos."""
    import time
    import traceback

    from main_pipeline import executar_pipeline

    intervalo = max(5, config.INTERVALO_COLETA_MIN) * 60
    while True:
        try:
            print(f"[AGENDADOR] Coletando (Selenium={config.USAR_SELENIUM})...")
            executar_pipeline(usar_selenium=config.USAR_SELENIUM)
        except Exception:
            print("[AGENDADOR] Falha no ciclo de coleta:")
            traceback.print_exc()
        time.sleep(intervalo)


def iniciar_agendador():
    """Sobe o agendador em thread daemon (uma vez por processo)."""
    import threading

    if getattr(iniciar_agendador, "_ligado", False):
        return
    iniciar_agendador._ligado = True
    threading.Thread(target=_ciclo_agendador, name="agendador",
                     daemon=True).start()
    print(f"[AGENDADOR] Ativo — coleta a cada "
          f"{config.INTERVALO_COLETA_MIN} min.")


# No Render (ou com AGENDADOR=1), o próprio web service mantém os dados
# atualizados — não é necessário um Cron Job separado.
if config.AGENDADOR_ATIVO:
    iniciar_agendador()


# ──────────────────────────────────────────────────────────────────────────
# EXECUÇÃO
# ──────────────────────────────────────────────────────────────────────────
def rodar_no_colab(porta: int = 8050):
    """No Colab (dash>=2.11): renderiza o dashboard inline no notebook."""
    app.run(jupyter_mode="inline", port=porta, debug=False)


if __name__ == "__main__":
    import os

    porta = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=porta, debug=not config.IN_RENDER)
