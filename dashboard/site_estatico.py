# -*- coding: utf-8 -*-
"""
site_estatico.py
================
Gera uma PÁGINA HTML AUTOCONTIDA a partir do snapshot — para publicar no
GitHub Pages (hospedagem gratuita, sem servidor, sem hibernar).

O visual acompanha o dashboard Dash: banner do estágio, cards Nível×Cota,
grid das 17 regiões, gauge e os gráficos Plotly (que continuam interativos),
tema claro/escuro e o crédito do CISC.

Uso:  gerar_site(snapshot, destino="site/index.html")
"""

from __future__ import annotations

from pathlib import Path

import config
from dashboard import componentes


# ──────────────────────────────────────────────────────────────────────────
# Blocos de HTML
# ──────────────────────────────────────────────────────────────────────────
def _bloco_fontes(snapshot: dict) -> str:
    fontes = snapshot.get("fontes") or {}
    fora = [n for n, ok in fontes.items() if not ok]
    if not fora:
        return ""
    return (
        '<div class="aviso-fontes">'
        f"<b>Atenção:</b> nesta coleta não foi possível consultar "
        f"{', '.join(fora)}. A classificação usa apenas as fontes disponíveis "
        "e pode estar subestimada — consulte os canais oficiais da Defesa Civil."
        "</div>"
    )


def _bloco_banner(snapshot: dict) -> str:
    cls = snapshot.get("classificacao") or {}
    cor = cls.get("cor", "#2E9E44")
    # O "⚑" (regra de piso) e o "⚙" (lista de gatilhos) já são mostrados
    # na seção "Gatilhos de campo confirmados" — não repetir no banner.
    justificativas = "".join(
        f"<div class='just'>{j}</div>"
        for j in cls.get("justificativas", [])
        if not j.lstrip().startswith(("⚑", "⚙")))
    return f"""
    <section class="banner" style="background:{cor}">
      <h2>ESTÁGIO OPERACIONAL: {cls.get('rotulo') or cls.get('estagio', '—')}</h2>
      <div class="ts">Última atualização: {snapshot.get('timestamp', '—')}</div>
      {justificativas}
    </section>"""


def _bloco_cards(snapshot: dict) -> str:
    ind = snapshot.get("indicadores") or {}
    cards = []
    for info in config.INFO_RIOS_CARDS:
        nivel = componentes._nivel_do_indicador(ind, info["chave"])
        cota = info["cota_inundacao"]

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
            valor = (f"<div class='valor' style='color:{cor}'>{nivel:.2f} m"
                     f"<span class='cota'> / {cota:.2f} m</span></div>")
            barra = (f"<div class='trilho'><div class='barra' style='width:"
                     f"{min(pct, 100):.0f}%;background:{cor}'></div></div>")
            rodape = f"<div class='pct'>{pct:.0f}% da cota de inundação</div>"
        else:
            texto = f"{nivel:.2f} m" if nivel is not None else "—"
            valor = f"<div class='valor neutro'>{texto}</div>"
            barra = ""
            rodape = ("<div class='pct'>cota de inundação: não informada</div>"
                      if nivel is not None else "<div class='pct'>sem leitura</div>")

        cards.append(f"""
        <div class="card">
          <div class="rio">{info['rotulo']}</div>
          <div class="est">{info['municipio']} · est. {info['estacao']}</div>
          {valor}{barra}{rodape}
        </div>""")
    return f"<section class='cards'>{''.join(cards)}</section>"


def _bloco_regioes(snapshot: dict) -> str:
    alertas = (snapshot.get("indicadores") or {}).get("alertas_regionais") or []

    def grau(risco: str) -> int:
        """0=sem risco … 4=extremo (o mais grave vence, na ordem inversa)."""
        r = (risco or "").lower()
        for i, termo in reversed(list(enumerate(
                ("sem risco", "atenção", "alto", "muito alto", "extremo")))):
            if termo in r:
                return i
        return 0

    por_regiao: dict[int, dict] = {}
    for al in alertas:
        num = al.get("regiao_num")
        if num is None:
            continue
        atual = por_regiao.get(num)
        if atual is None or grau(al.get("risco")) > grau(atual.get("risco")):
            por_regiao[num] = al

    ordem = ["sem risco", "atenção", "alto", "muito alto", "extremo"]

    def tile(num: int) -> str:
        al = por_regiao.get(num)
        nome = (al or {}).get("regiao_nome") or config.REGIOES_POACLIMA.get(num, "")
        if al is None:
            cor = config.CORES_RISCO_POACLIMA["sem dado"]
            status, detalhe = "sem dado", ""
        else:
            cor = config.CORES_RISCO_POACLIMA.get(ordem[grau(al.get("risco"))],
                                                  "#4A5561")
            status = al.get("risco") or ""
            partes = [p for p in (al.get("tipo"),
                                  f"até {al.get('fim')}" if al.get("fim") else None) if p]
            detalhe = " · ".join(partes)
        return (f"<div class='tile' style='background:{cor}'>"
                f"<div class='num'>{num}</div><div class='nome'>{nome}</div>"
                f"<div class='status'>{status}</div>"
                f"<div class='detalhe'>{detalhe}</div></div>")

    # Tela: triângulo 8 / 6 / 3 · Impressão: 7 / 6 / 4 (cabe melhor na A4)
    def grade(faixas):
        return "".join(
            f"<div class='linha-regioes'>{''.join(tile(n) for n in faixa)}</div>"
            for faixa in faixas)

    html_linhas = (f"<div class='regioes-tela'>{grade([range(1, 9), range(9, 15), range(15, 18)])}</div>"
                   f"<div class='regioes-print'>{grade([range(1, 8), range(8, 14), range(14, 18)])}</div>")

    return f"""
    <section class="bloco-regioes">
      <h3 class="titulo-secao">Risco por região — Defesa Civil (Poaclima)</h3>
      <div class="sub">Status capturado dos marcadores do mapa oficial ·
        cinza = região sem dado nesta coleta</div>
      <div class="regioes">{html_linhas}</div>
    </section>"""


def _bloco_gatilhos(snapshot: dict) -> str:
    ativos = snapshot.get("gatilhos_ativos") or []
    if not ativos:
        return ""
    cor = (snapshot.get("classificacao") or {}).get("cor", "#F2830B")
    badges = "".join(
        f"<span class='badge' style='background:{cor}'>{a}</span>" for a in ativos)
    return f"""
    <h3 class="titulo-secao">Gatilhos de campo confirmados (SMS/Defesa Civil/CISC)</h3>
    <section class="gatilhos">{badges}</section>"""


def _bloco_graficos(snapshot: dict) -> str:
    """
    Cada gráfico é renderizado DUAS vezes (tema escuro e claro). O CSS mostra
    a versão certa conforme o tema — e na impressão força sempre a clara,
    senão o texto dos gráficos sai cinza-claro sobre papel branco.
    """
    construtores = [
        # (constrói, largura_print, altura_print, ocupa_linha_inteira)
        (lambda t: componentes.gauge_estagio(
            snapshot.get("classificacao") or {}, t), 330, 250, False),
        (lambda t: componentes.grafico_guaiba(
            snapshot.get("serie_guaiba", []), t), 330, 250, False),
        (lambda t: componentes.grafico_afluentes(
            snapshot.get("series_afluentes", {}), t), 330, 250, False),
        (lambda t: componentes.grafico_precipitacao(
            snapshot.get("serie_precipitacao_horaria", []),
            snapshot.get("serie_precipitacao_diaria", []), t,
            obs_inmet=snapshot.get("chuva_obs_inmet"),
            previsao_poa=snapshot.get("previsao_poaclima"),
            fonte_obs=snapshot.get("fonte_chuva_obs", "Open-Meteo"),
            fonte_prev=snapshot.get("fonte_chuva_prev", "Open-Meteo")),
         1000, 300, True),
    ]

    partes, primeiro = [], True
    for constroi, larg_print, alt_print, largo in construtores:
        blocos = []
        for tema in ("dark", "claro"):
            fig = constroi(tema)
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                              plot_bgcolor="rgba(0,0,0,0)", autosize=True,
                              margin=dict(l=50, r=30, t=60, b=40))
            if tema == "dark":
                # tela: acompanha a largura do cartão
                html_fig = fig.to_html(
                    full_html=False,
                    include_plotlyjs="cdn" if primeiro else False,
                    config={"displayModeBar": False, "responsive": True},
                    default_width="100%", default_height="340px")
            else:
                # Modo claro na TELA: responsivo, igual ao escuro (antes ficava
                # com largura fixa e "estourava" o cartão). O tamanho fixo de
                # impressão é aplicado por JS no evento beforeprint.
                html_fig = fig.to_html(
                    full_html=False, include_plotlyjs=False,
                    config={"displayModeBar": False, "responsive": True},
                    default_width="100%", default_height="340px")
            primeiro = False
            blocos.append(f"<div class='fig-{tema}'>{html_fig}</div>")
        classe = "grafico largo" if largo else "grafico"
        partes.append(f"<div class='{classe}' data-w='{larg_print}' "
                      f"data-h='{alt_print}'>{''.join(blocos)}</div>")
    return f"<section class='graficos'>{''.join(partes)}</section>"


_CSS = """
:root{--fundo:#101418;--cartao:#161C22;--txt:#E8ECF1;--txt2:#9AA6B2;
      --borda:#2A333D;--trilho:rgba(255,255,255,.10)}
body.claro{--fundo:#F2F4F7;--cartao:#FFFFFF;--txt:#1F2733;--txt2:#5A6472;
      --borda:#D9DEE5;--trilho:rgba(0,0,0,.10)}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px 40px;background:var(--fundo);color:var(--txt);
     font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
     text-align:center;transition:background .3s}
.wrap{max-width:1320px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 4px}
.sub{color:var(--txt2);font-size:.9rem;margin-bottom:14px}
.acoes{margin:10px 0 18px}
button{background:transparent;color:var(--txt);border:1px solid var(--borda);
       border-radius:8px;padding:8px 16px;font-size:.9rem;cursor:pointer;margin:0 4px}
button:hover{border-color:var(--txt2)}
.aviso-fontes{background:#8a6d1a;color:#fff;border-radius:10px;padding:10px 14px;
              margin-bottom:12px;font-size:.88rem;text-align:center}
.banner{border-radius:14px;padding:16px 20px;color:#fff;margin-bottom:18px}
.banner h2{margin:0 0 4px;font-size:1.8rem;letter-spacing:.5px}
.banner .ts{font-size:.85rem;opacity:.85;margin-bottom:8px}
.banner .just{font-size:.95rem;margin:3px 0}
.cards{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin-bottom:22px}
.card{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;
      padding:12px;flex:0 0 calc(20% - 12px);min-width:0}
@media(max-width:1100px){.card{flex:0 0 calc(33.33% - 12px)}}
@media(max-width:700px){.card{flex:0 0 calc(50% - 12px)}}
.card .rio{font-weight:700}
.card .est{color:var(--txt2);font-size:.76rem;margin-bottom:8px;min-height:30px}
.card .valor{font-size:1.6rem;font-weight:700}
.card .valor.neutro{color:var(--txt)}
.card .cota{font-size:.85rem;opacity:.75;font-weight:400}
.trilho{height:8px;border-radius:4px;background:var(--trilho);overflow:hidden;margin:6px 0}
.trilho .barra{height:100%;border-radius:4px}
.card .pct{color:var(--txt2);font-size:.76rem}
.titulo-secao{margin:22px 0 2px;font-size:1.05rem}
.regioes{margin-bottom:22px}
.linha-regioes{display:flex;gap:8px;justify-content:center;margin-bottom:8px}
.linha-regioes .tile{flex:0 0 calc(12.5% - 8px);min-width:0}
@media(max-width:900px){.linha-regioes{flex-wrap:wrap}
  .linha-regioes .tile{flex:0 0 calc(25% - 8px)}}
@media(max-width:560px){.linha-regioes .tile{flex:0 0 calc(50% - 8px)}}
.tile{border-radius:10px;padding:8px 6px;color:#fff;min-height:74px}
.tile .num{font-weight:700;font-size:.85rem;opacity:.9}
.tile .nome{font-weight:700;font-size:.82rem;line-height:1.15}
.tile .status{font-size:.78rem}
.tile .detalhe{font-size:.68rem;opacity:.85}
.gatilhos{margin-bottom:20px}
.badge{display:inline-block;color:#fff;border-radius:10px;padding:8px 14px;
       margin:4px;font-weight:700;font-size:.9rem}
.graficos{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:14px}
.grafico{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;
         padding:8px;min-width:0;overflow:hidden}
.grafico.largo{grid-column:1/-1}
.grafico .js-plotly-plot,.grafico .plot-container{width:100% !important}
.fig-claro{display:none;max-width:100%;overflow-x:auto}
.regioes-print{display:none}
body.claro .fig-dark{display:none}
body.claro .fig-claro{display:block}
.rodape{margin-top:26px}
.cisc{font-weight:700;margin-bottom:6px}
.mini{color:var(--txt2);font-size:.8rem;max-width:900px;margin:0 auto}
@media(max-width:600px){.graficos{grid-template-columns:1fr}}

/* ── IMPRESSÃO / PDF: paisagem, cores fiéis, gráficos no tema claro ── */
@page{size:A4 landscape;margin:10mm}
@media print{
  *{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important}
  body{background:#fff !important;color:#1F2733 !important;padding:0;
       --fundo:#fff;--cartao:#fff;--txt:#1F2733;--txt2:#5A6472;
       --borda:#CCD2D9;--trilho:rgba(0,0,0,.10)}
  .acoes{display:none !important}
  .fig-dark{display:none !important}
  .fig-claro{display:block !important}
  .banner,.card,.tile,.grafico,.bloco-regioes,.linha-regioes{
      break-inside:avoid;page-break-inside:avoid}
  .bloco-regioes{page-break-before:auto}
  .banner h2{font-size:1.5rem}
  .cards{display:grid !important;grid-template-columns:repeat(5,1fr);gap:8px}
  .card{max-width:none;flex:none !important}
  .regioes-tela{display:none !important}
  .regioes-print{display:block !important}
  .linha-regioes{margin-bottom:6px}
  .linha-regioes .tile{flex:0 0 calc(14.28% - 6px);min-height:0;padding:5px 4px}
  .graficos{display:flex;flex-wrap:wrap;justify-content:center;gap:6px}
  .grafico{margin:0;padding:2px;border:none}
  .grafico.largo{flex:0 0 100%}
  .card{padding:7px}
  .card .est{min-height:0}
  .titulo-secao{margin:8px 0 2px}
  .banner{padding:10px 14px;margin-bottom:10px}
  .graficos{display:block}
  .grafico{display:inline-block;vertical-align:top;width:auto;margin:0 4px 8px}
  .grafico.largo{display:block}
  .grafico .fig-claro{overflow:visible}
  h1{font-size:1.4rem}
}
"""

# Aplica o tema salvo ANTES dos gráficos serem desenhados (senão o Plotly
# desenha a versão visível com tamanho zero e o layout sai torto).
_JS_CEDO = """
(function(){try{if(localStorage.getItem('tema')==='claro'){
  document.documentElement.classList.add('pre-claro');}}catch(e){}})();
"""

_JS = """
const b=document.body, bt=document.getElementById('btn-tema');
if(document.documentElement.classList.contains('pre-claro')){b.classList.add('claro');}
function rotulo(){bt.textContent=b.classList.contains('claro')?'🌙 Modo escuro':'☀ Modo claro';}
rotulo();
bt.onclick=()=>{
  const claro=!b.classList.contains('claro');
  localStorage.setItem('tema', claro?'claro':'dark');
  location.reload();
};
function ajustarGraficos(){   // ajusta o tema que estiver visível
  document.querySelectorAll('.js-plotly-plot').forEach(function(g){
    if(g.offsetParent!==null){try{Plotly.Plots.resize(g);}catch(e){}}
  });
}
function medidasDeImpressao(){   // A4 paisagem: tamanho fixo e previsível
  document.querySelectorAll('.grafico').forEach(function(box){
    var w=+box.dataset.w, h=+box.dataset.h;
    box.querySelectorAll('.fig-claro .js-plotly-plot').forEach(function(g){
      try{Plotly.relayout(g,{width:w,height:h,autosize:false});}catch(e){}
    });
  });
}
function medidasDeTela(){
  document.querySelectorAll('.fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,width:null,height:340});}catch(e){}
  });
  ajustarGraficos();
}
window.addEventListener('beforeprint', medidasDeImpressao);
window.addEventListener('afterprint', medidasDeTela);
window.addEventListener('load', function(){setTimeout(ajustarGraficos, 120);
                                           setTimeout(ajustarGraficos, 600);});
window.addEventListener('resize', ajustarGraficos);

document.getElementById('btn-print').onclick=()=>{ window.print(); };
"""


def gerar_site(snapshot: dict, destino: str | Path = "site/index.html",
               tema: str = "dark") -> str:
    """Gera o HTML autocontido e retorna o caminho do arquivo."""
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="900">
<title>Estágios Operacionais — Porto Alegre</title>
<style>{_CSS}</style>
<script>{_JS_CEDO}</script>
</head>
<body class="{'claro' if tema == 'claro' else ''}">
<div class="wrap">
  <h1>Plano de Contingência — Estágios Operacionais</h1>
  <div class="sub">Porto Alegre/RS · SMS/PMPA · monitoramento automatizado
    (ANA · Open-Meteo · INMET · Poaclima)</div>
  <div class="acoes">
    <button id="btn-tema">☀ Modo claro</button>
    <button id="btn-print">🖨 Imprimir / PDF</button>
  </div>
  {_bloco_fontes(snapshot)}
  {_bloco_banner(snapshot)}
  {_bloco_cards(snapshot)}
  {_bloco_regioes(snapshot)}
  {_bloco_gatilhos(snapshot)}
  {_bloco_graficos(snapshot)}
  <div class="rodape">
    <div class="cisc">Realizado por: CISC Porto Alegre — Centro de Informações
      em Saúde e Clima</div>
    <div class="mini">Cotas de referência do Guaíba no Cais Mauá: atenção
      {config.COTA_ATENCAO_GUAIBA} m · alerta {config.COTA_ALERTA_GUAIBA} m ·
      inundação {config.COTA_INUNDACAO_GUAIBA} m (fonte: Poaclima/Defesa Civil
      de Porto Alegre). Cada régua tem referência de nível própria, por isso as
      leituras de estações diferentes não são comparáveis entre si.
      Ferramenta de apoio à decisão — não substitui os canais oficiais da
      Defesa Civil.</div>
  </div>
</div>
<script>{_JS}</script>
</body></html>"""

    destino.write_text(html, encoding="utf-8")
    print(f"[SITE] Página gerada: {destino} ({len(html)/1024:.0f} KB)")
    return str(destino)


if __name__ == "__main__":
    import json
    caminho = config.DADOS_DIR / "ultimo_snapshot.json"
    if not caminho.exists():
        raise SystemExit("Rode o pipeline antes (main_pipeline.py).")
    gerar_site(json.loads(caminho.read_text(encoding="utf-8")))
