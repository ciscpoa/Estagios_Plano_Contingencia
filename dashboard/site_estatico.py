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
def _texto_html(txt: str) -> str:
    """Escapa HTML e converte quebras de linha em <br>, preservando o
    recuo visual dos itens '•' (o motivo agora é multilinha)."""
    import html as _html
    if not txt:
        return ""
    seguro = _html.escape(str(txt)).replace("\n\n", "<br><br>").replace("\n", "<br>")
    return seguro.replace("• ", "&nbsp;&nbsp;• ")


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
        f"<div class='just'>{_texto_html(j)}</div>"
        for j in cls.get("justificativas", [])
        if not j.lstrip().startswith(("⚑", "⚙")))
    return f"""
    <section class="banner" style="background:{cor}">
      <h2>ESTÁGIO OPERACIONAL: {cls.get('rotulo') or cls.get('estagio', '—')}</h2>
      <div class="ts">Última atualização: {snapshot.get('timestamp', '—')}
        <span id="frescor" class="frescor" data-iso="{snapshot.get('timestamp_iso', '')}"></span>
      </div>
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


def _bloco_avisos_inmet(snapshot: dict) -> str:
    """Retângulo com os avisos meteorológicos vigentes do INMET para POA."""
    av = snapshot.get("avisos_inmet") or {}
    alertas = av.get("alertas") or []

    if not av.get("consultado", True):
        return ("<section class='avisos-inmet indisponivel'>"
                "<div class='titulo-aviso'>Avisos do INMET</div>"
                "<div class='texto-aviso'>Não foi possível consultar o INMET "
                "nesta atualização — verifique em alertas2.inmet.gov.br</div>"
                "</section>")

    if not alertas:
        return ("<section class='avisos-inmet sem-aviso'>"
                "<div class='titulo-aviso'>Avisos do INMET</div>"
                "<div class='texto-aviso'><b>Nenhum aviso meteorológico "
                "vigente</b> para Porto Alegre no momento.</div>"
                "</section>")

    itens = []
    for a in alertas[:4]:
        sev = a.get("severidade") or "Amarelo"
        cor = config.CORES_AVISO_INMET.get(sev, "#E3B505")
        periodo = " · ".join(p for p in (
            f"de {a['inicio']}" if a.get("inicio") else None,
            f"até {a['fim']}" if a.get("fim") else None) if p)
        itens.append(
            f"<div class='item-aviso' style='border-left:6px solid {cor}'>"
            f"<span class='sev' style='background:{cor}'>{sev}</span>"
            f"<span class='desc'>{(a.get('descricao') or '').strip()[:220]}</span>"
            + (f"<div class='periodo'>{periodo}</div>" if periodo else "")
            + "</div>")
    return (f"<section class='avisos-inmet'>"
            f"<div class='titulo-aviso'>Avisos meteorológicos vigentes — INMET"
            f" ({len(alertas)})</div>{''.join(itens)}</section>")


def _bloco_arvore(snapshot: dict) -> str:
    """
    Árvore das regras E/OU do Plano: mostra quais blocos do estágio atual
    estão ATIVOS (destacados) e quais não (ofuscados), e o que falta para
    subir para o próximo estágio.
    """
    cls = snapshot.get("classificacao") or {}
    blocos = cls.get("blocos_por_estagio") or {}
    estagio = cls.get("estagio")
    if not blocos or not estagio:
        return ""

    cor = cls.get("cor", "#2E9E44")
    ordem = config.ESTAGIOS
    idx = ordem.index(estagio) if estagio in ordem else 0
    proximo = ordem[idx + 1] if idx + 1 < len(ordem) else None

    def linha(nome: str, cor_linha: str, atual: bool) -> str:
        bl = blocos.get(nome) or []
        if not bl:
            return ""
        caixas = []
        for i, b in enumerate(bl):
            classe = "no-arvore ativo" if b["ativo"] else "no-arvore inativo"
            estilo = (f"background:{cor_linha};border-color:{cor_linha}"
                      if b["ativo"] else "")
            marca = "✔" if b["ativo"] else "✖"
            motivo = (b.get("motivo") or "").strip()
            # o motivo explica POR QUE o bloco está (ou não) ativo — sem ele
            # a árvore vira um "sim/não" sem auditoria
            html_motivo = (f"<span class='motivo-no'>{_texto_html(motivo)}</span>"
                           if motivo else "")
            dica = motivo.replace("\n", " · ").replace("'", "&#39;")
            caixas.append(
                f"<div class='{classe}' style='{estilo}' title='{dica}'>"
                f"<span class='marca'>{marca}</span>"
                f"<span class='rotulo'>{b['titulo']}</span>"
                f"{html_motivo}</div>")
            if i < len(bl) - 1:
                caixas.append("<div class='conector'>E</div>")
        subtitulo = ("estágio atual — todos os blocos precisam estar ativos"
                     if atual else
                     "para subir de estágio, faltam os blocos ofuscados")
        return (f"<div class='linha-arvore'>"
                f"<div class='rotulo-linha' style='color:{cor_linha}'>{nome}</div>"
                f"<div class='sub-arvore'>{subtitulo}</div>"
                f"<div class='nos'>{''.join(caixas)}</div></div>")

    partes = [linha(estagio, cor, True)]
    if proximo:
        partes.append(linha(proximo, config.CORES_ESTAGIOS.get(proximo, "#888"),
                            False))

    nota = ""
    if any("⚑" in j for j in cls.get("justificativas", [])):
        nota = ("<div class='nota-arvore'>⚑ Este estágio foi definido pela "
                "<b>regra de piso</b>: um gatilho confirmado em campo pertence "
                "a esta coluna do Plano, então o estágio sobe mesmo sem todos "
                "os blocos meteorológicos fecharem.</div>")

    return f"""
    <section class="bloco-arvore">
      <h3 class="titulo-secao">Como chegamos a este estágio</h3>
      <div class="sub">Regras E/OU do Plano de Contingência (item 5.1) ·
        blocos <b>ativos</b> em destaque, inativos ofuscados</div>
      {''.join(partes)}{nota}
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
            fonte_prev=snapshot.get("fonte_chuva_prev", "Open-Meteo"),
            obs_diaria=snapshot.get("serie_obs_diaria")),
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
    return (f"<section class='graficos'>{''.join(partes)}</section>"
            + _rodape_chuva(snapshot))


def _rodape_chuva(snapshot: dict) -> str:
    """
    Card de chuva: 5 dias para trás × 5 dias para frente, lado a lado.

    As cores dos números espelham as do gráfico de precipitação — laranja
    para o acumulado observado, magenta para a previsão do Poaclima — para
    que o leitor ligue o número à linha correspondente sem legenda.

    Nada de metainformação de coleta aqui: quantas fontes foram testadas
    é assunto de depuração e vive no CSV e no log, não no painel público.
    """
    obs = snapshot.get("chuva_obs_5d_mm")
    prev = snapshot.get("chuva_prev_5d_mm")
    if obs is None and prev is None:
        return ""

    fonte_obs = snapshot.get("fonte_chuva_obs") or "—"
    fonte_prev = snapshot.get("fonte_chuva_prev") or "Poaclima/Catavento"

    def coluna(titulo, fonte, valor, periodo, cor):
        num = f"{valor:.0f} mm" if isinstance(valor, (int, float)) else "—"
        return f"""
        <div class="col-chuva">
          <div class="titulo-chuva">{titulo}</div>
          <div class="fonte-chuva">{fonte}</div>
          <div class="valor-chuva" style="color:{cor}">{num}</div>
          <div class="periodo-chuva">{periodo}</div>
        </div>"""

    return f"""
    <section class="cartao-chuva">
      {coluna("CHUVA OBSERVADA", fonte_obs, obs, "últimos 5 dias", "#F2830B")}
      <div class="divisor-chuva"></div>
      {coluna("CHUVA PREVISTA", fonte_prev, prev, "próximos 5 dias", "#E5399B")}
    </section>"""


_JS_FRESCOR = """
<script>
/* O cron do GitHub Actions falha/atrasa com frequência. Sem este aviso, um
   painel parado parece um painel calmo — que é o pior modo de falhar numa
   ferramenta de contingência. */
(function () {
  var el = document.getElementById("frescor");
  if (!el || !el.dataset.iso) return;
  function tick() {
    var min = (Date.now() - new Date(el.dataset.iso).getTime()) / 60000;
    el.className = "frescor";
    if (min >= 180) {
      el.classList.add("parado");
      el.textContent = "PARADO ha " + Math.floor(min / 60) + "h";
    } else if (min >= 75) {
      el.classList.add("velho");
      el.textContent = "desatualizado ha " + Math.round(min) + " min";
    } else {
      el.textContent = "";
    }
  }
  tick();
  setInterval(tick, 60000);
})();
</script>
"""

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
.avisos-inmet{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:10px 14px;margin-bottom:16px;text-align:left}
.avisos-inmet.sem-aviso{border-color:#2E9E44}
.avisos-inmet.indisponivel{border-color:#8B95A1}
.titulo-aviso{font-weight:700;text-align:center;margin-bottom:6px}
.texto-aviso{text-align:center;font-size:.92rem;color:var(--txt2)}
.avisos-inmet.sem-aviso .texto-aviso{color:var(--txt)}
.item-aviso{padding:6px 10px;margin:6px 0;background:rgba(127,127,127,.08);
  border-radius:8px}
.item-aviso .sev{display:inline-block;color:#fff;font-weight:700;font-size:.78rem;
  border-radius:6px;padding:2px 8px;margin-right:8px}
.item-aviso .desc{font-size:.9rem}
.item-aviso .periodo{font-size:.78rem;color:var(--txt2);margin-top:3px}
.bloco-arvore{margin-bottom:22px}
.linha-arvore{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:10px 12px;margin-bottom:10px}
.rotulo-linha{font-weight:800;letter-spacing:.4px}
.sub-arvore{color:var(--txt2);font-size:.78rem;margin-bottom:8px}
.nos{display:flex;flex-wrap:wrap;align-items:stretch;justify-content:center;gap:6px}
.no-arvore{flex:1 1 240px;max-width:360px;border:1px solid var(--borda);
  border-radius:10px;padding:8px 10px;display:grid;
  grid-template-columns:auto 1fr;gap:4px 8px;align-items:start;
  text-align:left;font-size:.84rem}
.no-arvore.ativo{color:#fff;font-weight:600}
.no-arvore.inativo{opacity:.45}
.no-arvore .marca{font-weight:800}
.no-arvore .rotulo{grid-column:2}
.motivo-no{grid-column:2;font-size:.74rem;font-weight:400;line-height:1.35;
  opacity:.85;border-top:1px solid rgba(255,255,255,.22);padding-top:5px;
  margin-top:2px}
.no-arvore.inativo .motivo-no{border-top-color:var(--borda)}
.conector{align-self:center;font-weight:800;color:var(--txt2);padding:0 2px}
.nota-arvore{font-size:.82rem;color:var(--txt2);margin-top:6px}
.cartao-chuva{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:16px 20px;margin:10px 0;display:flex;
  align-items:stretch;justify-content:center;gap:8px;flex-wrap:wrap}
.col-chuva{flex:1 1 240px;max-width:420px;text-align:center;padding:4px 12px}
.divisor-chuva{width:1px;background:var(--borda);align-self:stretch}
.titulo-chuva{font-weight:700;font-size:.82rem;color:var(--txt2);
  text-transform:uppercase;letter-spacing:.5px}
.fonte-chuva{font-weight:700;font-size:.95rem;color:var(--txt2);margin-top:2px}
.valor-chuva{font-weight:800;font-size:2.1rem;line-height:1.2;margin-top:8px}
.periodo-chuva{color:var(--txt2);font-size:.78rem;margin-top:2px}
@media(max-width:640px){.divisor-chuva{width:100%;height:1px}}
.just{line-height:1.5}
.frescor{display:none;margin-left:8px;padding:2px 8px;border-radius:999px;
  font-size:.72rem;font-weight:700;vertical-align:middle}
.frescor.velho{display:inline-block;background:#FFD166;color:#3A2E00}
.frescor.parado{display:inline-block;background:#D62828;color:#fff}
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
  .banner,.card,.tile,.grafico,.bloco-regioes,.linha-regioes,.avisos-inmet,.linha-arvore{
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
  {_bloco_avisos_inmet(snapshot)}
  {_bloco_cards(snapshot)}
  {_bloco_regioes(snapshot)}
  {_bloco_arvore(snapshot)}
  {_bloco_gatilhos(snapshot)}
  {_bloco_graficos(snapshot)}
  {_JS_FRESCOR}
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
