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
_RAIZ = Path(__file__).resolve().parent.parent


def _ativo_b64(nome: str, mime: str) -> str:
    """
    Lê um arquivo de assets/ e devolve um data URI.

    Embutir em base64 deixa a página autocontida: um único index.html, sem
    caminho relativo para quebrar no GitHub Pages e sem requisição externa
    na hora de imprimir o PDF (imagem faltando em PDF é falha silenciosa).
    """
    caminho = _RAIZ / "assets" / nome
    try:
        import base64
        return (f"data:{mime};base64,"
                + base64.b64encode(caminho.read_bytes()).decode("ascii"))
    except Exception:
        return ""


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


def _trilho_estagios(atual: str) -> str:
    """
    Reproduz a progressão em chevrons do item 5.1 do Plano.

    O banner sozinho diz em que estágio a cidade está; o trilho diz em que
    DEGRAU da escala isso fica e qual é o próximo — que é a informação que
    um operador precisa para antecipar. O desenho é o do próprio Plano, não
    um enfeite: a fonte da escala é o documento oficial.
    """
    def _rgba(hexa: str, alfa: float) -> str:
        h = hexa.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{alfa})"

    passos = []
    idx_atual = (config.ESTAGIOS.index(atual)
                 if atual in config.ESTAGIOS else -1)
    for i, nome in enumerate(config.ESTAGIOS):
        cor = config.CORES_ESTAGIOS[nome]
        if i == idx_atual:
            classe, estilo = "passo atual", f"background:{cor};border-color:{cor}"
        else:
            # Antes os degraus inativos viviam só de opacidade e sumiam no
            # fundo escuro. Agora cada um leva um preenchimento na própria
            # cor: continua claramente secundário, mas legível.
            classe = "passo antes" if i < idx_atual else "passo depois"
            estilo = (f"border-color:{cor};color:{cor};"
                      f"background:{_rgba(cor, .16 if i < idx_atual else .10)}")
        curto = "EMERGÊNCIA" if nome.startswith("SITUAÇÃO") else nome
        passos.append(f"<div class='{classe}' style='{estilo}'>"
                      f"<span class='grau'>{i + 1}</span>{curto}</div>")
    return f"<div class='trilho-estagios'>{''.join(passos)}</div>"


def _linha_blocos(blocos: list, cor_linha: str, subtitulo: str,
                  nome: str | None = None) -> str:
    """Fileira BLOCO · E · BLOCO · E · BLOCO de um estágio."""
    if not blocos:
        return ""
    caixas = []
    for i, b in enumerate(blocos):
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
        if i < len(blocos) - 1:
            caixas.append("<div class='conector'>E</div>")
    cabeca = (f"<div class='rotulo-linha' style='color:{cor_linha}'>{nome}</div>"
              if nome else "")
    return (f"<div class='linha-arvore'>{cabeca}"
            f"<div class='sub-arvore'>{subtitulo}</div>"
            f"<div class='nos'>{''.join(caixas)}</div></div>")


def _bloco_banner(snapshot: dict) -> str:
    cls = snapshot.get("classificacao") or {}
    cor = cls.get("cor", "#2E9E44")
    estagio = cls.get("estagio", "")
    blocos = (cls.get("blocos_por_estagio") or {}).get(estagio) or []

    # As justificativas do banner eram o MESMO texto dos motivos dos blocos.
    # Com os blocos aqui dentro, repeti-las seria dizer duas vezes a mesma
    # coisa — então o banner passa a mostrar só os blocos.
    corpo = _linha_blocos(
        blocos, cor, "estágio atual — todos os blocos precisam estar ativos")

    nota = ""
    if any("⚑" in j for j in cls.get("justificativas", [])):
        nota = ("<div class='nota-piso'>⚑ Estágio definido pela "
                "<b>regra de piso</b>: um gatilho confirmado em campo pertence "
                "a esta coluna do Plano, então o estágio sobe mesmo sem todos "
                "os blocos meteorológicos fecharem.</div>")

    return f"""
    {_trilho_estagios(estagio)}
    <section class="banner" style="border-color:{cor}">
      <div class="faixa-estagio" style="background:{cor}">
        <h2>ESTÁGIO OPERACIONAL: {cls.get('rotulo') or estagio or '—'}</h2>
        <div class="ts">Última atualização: {snapshot.get('timestamp', '—')}
          <span id="frescor" class="frescor" data-iso="{snapshot.get('timestamp_iso', '')}"></span>
        </div>
      </div>
      {corpo}{nota}
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
    # Distinção que faltava: região sem MARCADOR no mapa não é região sem
    # dado — é região sem alerta. "Sem dado" só se o Poaclima não respondeu.
    poaclima_ok = bool((snapshot.get("fontes") or {}).get("Poaclima"))
    rotulo_vazio = "sem alerta" if poaclima_ok else "sem dado"

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
            status, detalhe = rotulo_vazio, ""
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
        cinza = {"região sem alerta vigente" if poaclima_ok
                 else "Poaclima não respondeu nesta coleta"}</div>
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
            snapshot.get("classificacao") or {}, t), 1040, 268, True),
        (lambda t: componentes.grafico_guaiba(
            snapshot.get("serie_guaiba", []), t), 1040, 268, True),
        (lambda t: componentes.grafico_afluentes(
            snapshot.get("series_afluentes", {}), t), 1040, 268, True),
        (lambda t: componentes.grafico_precipitacao(
            snapshot.get("serie_precipitacao_horaria", []),
            snapshot.get("serie_precipitacao_diaria", []), t,
            obs_inmet=snapshot.get("chuva_obs_inmet"),
            previsao_poa=snapshot.get("previsao_poaclima"),
            fonte_obs=snapshot.get("fonte_chuva_obs", "Open-Meteo"),
            fonte_prev=snapshot.get("fonte_chuva_prev", "Open-Meteo"),
            obs_diaria=snapshot.get("serie_obs_diaria")),
         1040, 268, True),
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
/* Frescor do painel.

   Dois problemas distintos, que antes se confundiam num número só:
     • a COLETA pode ter parado (cron do GitHub descartado);
     • a PÁGINA pode estar velha em cache, mesmo com coleta nova no ar.

   O index.html carrega assets embutidos e é grande, então o CDN do Pages e
   o navegador o guardam. Por isso a idade é medida pelo status.json, que é
   buscado com cache desativado: se houver coleta nova, a página se recarrega
   sozinha com parâmetro anti-cache; se não houver, o selo mostra a idade
   verdadeira do dado. */
(function () {
  var el = document.getElementById("frescor");
  if (!el) return;
  var isoAtual = el.dataset.iso || "";

  function pinta(iso) {
    if (!iso) return;
    var min = (Date.now() - new Date(iso).getTime()) / 60000;
    el.className = "frescor";
    if (min >= 120) {
      el.classList.add("parado");
      el.textContent = "PARADO há " + Math.floor(min / 60) + "h";
    } else if (min >= 60) {
      el.classList.add("velho");
      el.textContent = "desatualizado há " + Math.round(min) + " min";
    } else {
      el.textContent = "";
    }
  }

  function consultaServidor() {
    fetch("status.json?v=" + Date.now(), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.timestamp_iso) return;
        var maisNova = isoAtual &&
                       new Date(d.timestamp_iso) > new Date(isoAtual);
        if (maisNova) {
          /* TRAVA obrigatória: se o CDN insistir em servir o HTML antigo, a
             recarga não resolve e sem esta guarda a página entra em laço
             infinito. Tentamos UMA vez por versão; se voltar velha, paramos
             de recarregar e apenas mostramos a idade real do dado. */
          var chave = "recarga:" + d.timestamp_iso;
          var jaTentou = false;
          try { jaTentou = !!sessionStorage.getItem(chave); } catch (e) {}
          if (!jaTentou) {
            try { sessionStorage.setItem(chave, "1"); } catch (e) {}
            location.replace(location.pathname + "?v=" + Date.now());
            return;
          }
        }
        pinta(d.timestamp_iso);
      })
      .catch(function () { /* offline: segue com o horário embutido */ });
  }

  pinta(isoAtual);
  setInterval(function () { pinta(isoAtual); }, 60000);
  consultaServidor();
  setInterval(consultaServidor, 120000);   // a cada 2 min
})();
</script>
"""

_CSS = """
/* Paleta tirada do próprio assunto: a água barrenta do Guaíba e o azul do
   CISC. Fundo azul-esverdeado escuro em vez de cinza neutro — é água, não
   painel genérico. Bordas em branco/preto conforme pedido, com alfa para
   marcarem o contorno sem ofuscar o conteúdo. */
:root{--fundo:#0A141C;--cartao:#10202C;--txt:#E9EFF5;--txt2:#8FA3B4;
      --borda:rgba(255,255,255,.58);--borda-fina:rgba(255,255,255,.16);
      --trilho:rgba(255,255,255,.12);--cisc:#5B9BF3;--sombra:rgba(0,0,0,.35)}
body.claro{--fundo:#EDF1F5;--cartao:#FFFFFF;--txt:#132030;--txt2:#54657A;
      --borda:rgba(0,0,0,.52);--borda-fina:rgba(0,0,0,.14);
      --trilho:rgba(0,0,0,.10);--cisc:#1D4FA3;--sombra:rgba(20,40,60,.12)}
*{box-sizing:border-box}
body{margin:0;padding:22px 16px 40px;background:var(--fundo);color:var(--txt);
     font-family:"Barlow",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
     text-align:center;transition:background .3s;position:relative;min-height:100vh}
/* Guaíba ao fundo: atmosfera, não ilustração — sai do caminho antes do conteúdo */
body::before{content:"";position:fixed;inset:0;z-index:-1;
     background-size:cover;background-position:center 28%;
     background-repeat:no-repeat;opacity:.85}
.wrap{max-width:1320px;margin:0 auto;position:relative}
.cabecalho{display:flex;align-items:center;justify-content:center;gap:16px;
     text-align:left;margin-bottom:6px;flex-wrap:wrap}
.logo{height:62px;width:52px;flex:0 0 auto}
.sobretitulo{font-family:"Barlow Condensed",sans-serif;font-weight:600;
     font-size:.82rem;letter-spacing:.14em;text-transform:uppercase;
     color:var(--cisc)}
h1{font-family:"Barlow Condensed","Arial Narrow",sans-serif;font-weight:700;
     font-size:2.1rem;line-height:1.05;margin:2px 0 3px;letter-spacing:.01em}
h1 .fina{font-weight:500;color:var(--txt2)}
.sub{color:var(--txt2);font-size:.86rem;margin-bottom:0}
.acoes{margin:14px 0 18px}
button{background:transparent;color:var(--txt);border:1px solid var(--borda);
       border-radius:8px;padding:8px 16px;font-size:.88rem;cursor:pointer;
       margin:0 4px;font-family:inherit;transition:background .15s}
button:hover{background:rgba(127,160,190,.16)}
button:focus-visible{outline:2px solid var(--cisc);outline-offset:2px}
/* Trilho de estágios — a progressão em chevrons do item 5.1 do Plano */
.trilho-estagios{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}
.passo{flex:1 1 0;min-width:110px;position:relative;padding:9px 8px 9px 20px;
     font-family:"Barlow Condensed",sans-serif;font-weight:700;font-size:.86rem;
     letter-spacing:.05em;border:1.5px solid;border-radius:4px;
     clip-path:polygon(0 0,calc(100% - 12px) 0,100% 50%,calc(100% - 12px) 100%,0 100%,12px 50%)}
.passo .grau{display:block;font-size:.66rem;opacity:.75;font-weight:600}
.passo.atual{color:#fff;transform:scale(1.03);box-shadow:0 3px 14px var(--sombra)}
.passo.antes{opacity:.95}
.passo.depois{opacity:.82}
@media(max-width:760px){.passo{clip-path:none;flex:1 1 45%;padding:8px}}
.aviso-fontes{background:#8a6d1a;color:#fff;border-radius:10px;padding:10px 14px;
              margin-bottom:12px;font-size:.88rem;text-align:center}
.banner{border-radius:14px;margin-bottom:18px;background:var(--cartao);
      border:2px solid;box-shadow:0 4px 18px var(--sombra);overflow:hidden}
.faixa-estagio{color:#fff;padding:14px 20px 12px}
.banner .linha-arvore{border:none;background:transparent;margin:0;padding:12px}
.nota-piso{font-size:.82rem;color:var(--txt2);padding:0 12px 12px}
.banner h2{margin:0 0 2px;font-size:2rem;letter-spacing:.03em;
      font-family:"Barlow Condensed",sans-serif;font-weight:700}
.banner .ts{font-size:.85rem;opacity:.9;margin-bottom:0}
.banner .just{font-size:.95rem;margin:3px 0}
.cards{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;margin-bottom:22px}
.card{background:var(--cartao);border:1px solid var(--borda);border-radius:12px;
      padding:12px;flex:0 0 calc(20% - 12px);min-width:0;
      box-shadow:0 2px 10px var(--sombra)}
@media(max-width:1100px){.card{flex:0 0 calc(33.33% - 12px)}}
@media(max-width:700px){.card{flex:0 0 calc(50% - 12px)}}
.card .rio{font-weight:700;font-family:"Barlow Condensed",sans-serif;
      font-size:1.06rem;letter-spacing:.02em}
.card .est{color:var(--txt2);font-size:.76rem;margin-bottom:8px;min-height:30px}
.card .valor{font-size:1.62rem;font-weight:600;font-family:"IBM Plex Mono",
      ui-monospace,monospace;font-variant-numeric:tabular-nums}
.card .valor.neutro{color:var(--txt)}
.card .cota{font-size:.85rem;opacity:.75;font-weight:400}
.trilho{height:8px;border-radius:4px;background:var(--trilho);overflow:hidden;margin:6px 0}
.trilho .barra{height:100%;border-radius:4px}
.card .pct{color:var(--txt2);font-size:.76rem}
.titulo-secao{margin:24px 0 2px;font-size:1.18rem;
      font-family:"Barlow Condensed",sans-serif;font-weight:700;
      letter-spacing:.04em;text-transform:uppercase}
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
.linha-arvore{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:10px 12px;margin-bottom:10px}
.rotulo-linha{font-weight:800;letter-spacing:.4px}
.sub-arvore{color:var(--txt2);font-size:.78rem;margin-bottom:8px}
.nos{display:flex;flex-wrap:wrap;align-items:stretch;justify-content:center;gap:6px}
.no-arvore{flex:1 1 240px;max-width:360px;border:1px solid var(--borda-fina);
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
.no-arvore.inativo .motivo-no{border-top-color:var(--borda-fina)}
.conector{align-self:center;font-weight:800;color:var(--txt2);padding:0 2px}
.nota-arvore{font-size:.82rem;color:var(--txt2);margin-top:6px}
.cartao-chuva{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:16px 20px;margin:10px 0;display:flex;
  align-items:stretch;justify-content:center;gap:8px;flex-wrap:wrap}
.col-chuva{flex:1 1 240px;max-width:420px;text-align:center;padding:4px 12px}
.divisor-chuva{width:1px;background:var(--borda-fina);align-self:stretch}
.titulo-chuva{font-weight:700;font-size:.82rem;color:var(--txt2);
  text-transform:uppercase;letter-spacing:.5px}
.fonte-chuva{font-weight:700;font-size:.95rem;color:var(--txt2);margin-top:2px}
.valor-chuva{font-weight:600;font-size:2.2rem;line-height:1.2;margin-top:8px;
      font-family:"IBM Plex Mono",ui-monospace,monospace;
      font-variant-numeric:tabular-nums}
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
         padding:8px;min-width:0;overflow:hidden;position:relative;
         box-shadow:0 2px 10px var(--sombra)}
.grafico.largo{grid-column:1/-1}
@media screen{.grafico .js-plotly-plot,.grafico .plot-container{width:100%}}
/* A figura do tema inativo NÃO pode usar display:none: sem caixa de layout
   o Plotly não consegue dimensioná-la e ela sai em branco no PDF. Fica
   fora da tela, mas renderizada. */
.fig-oculta{position:absolute !important;left:-30000px !important;top:0 !important;
  width:1040px !important;pointer-events:none}
.fig-claro{position:absolute;left:-30000px;top:0;width:1040px;pointer-events:none}
body.claro .fig-claro{position:static;left:auto;width:auto;pointer-events:auto}
body.claro .fig-dark{position:absolute;left:-30000px;top:0;width:1040px;
  pointer-events:none}
.regioes-print{display:none}
.rodape{margin-top:30px;padding-top:18px;border-top:1px solid var(--borda-fina)}
.logo-rodape{height:46px;width:40px;opacity:.9;margin:0 auto 6px}
.cisc{font-weight:700;margin-bottom:6px;font-family:"Barlow Condensed",sans-serif;
  font-size:1.05rem;letter-spacing:.03em}
.mini{color:var(--txt2);font-size:.8rem;max-width:900px;margin:0 auto}
@media(max-width:600px){.graficos{grid-template-columns:1fr}}

/* ── IMPRESSÃO / PDF ────────────────────────────────────────────────
   O botão 🖨 usa o diálogo do navegador, então é ESTE bloco que define o
   PDF. A4 paisagem, cores fiéis, e quebras controladas: no PDF anterior os
   gráficos eram cortados no meio e os títulos truncavam. */
@page{size:A4 landscape;margin:9mm}
@media print{
  *{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important}
  body{background:#fff !important;color:#132030 !important;padding:0;
       --fundo:#fff;--cartao:#fff;--txt:#132030;--txt2:#54657A;
       --borda:rgba(0,0,0,.55);--borda-fina:rgba(0,0,0,.18);
       --trilho:rgba(0,0,0,.10);--sombra:transparent}
  body::before{display:none !important}
  .acoes,.frescor{display:none !important}
  .fig-dark{position:absolute !important;left:-30000px !important;top:0 !important;
       width:1040px !important}
  .fig-claro{position:static !important;left:auto !important;width:auto !important}
  .wrap{max-width:none}

  /* Cabeçalho compacto na primeira página */
  .cabecalho{gap:12px;margin-bottom:4px}
  .logo{height:44px;width:37px}
  h1{font-size:1.5rem}
  .sub,.sobretitulo{font-size:.72rem}

  .trilho-estagios{margin-bottom:8px}
  .passo{font-size:.72rem;padding:6px 6px 6px 16px}
  .banner{padding:10px 14px;margin-bottom:10px;box-shadow:none}
  .banner h2{font-size:1.45rem}
  .banner .just{font-size:.82rem}

  /* Nada pode ser partido ao meio entre páginas */
  .banner,.card,.tile,.grafico,.bloco-regioes,.linha-regioes,.avisos-inmet,
  .linha-arvore,.cartao-chuva,.trilho-estagios,.no-arvore{
      break-inside:avoid;page-break-inside:avoid}

  .cards{display:grid !important;grid-template-columns:repeat(5,1fr);gap:7px}
  .card{max-width:none;flex:none !important;padding:7px;box-shadow:none}
  .card .est{min-height:0}
  .card .valor{font-size:1.3rem}

  .regioes-tela{display:none !important}
  .regioes-print{display:block !important}
  .linha-regioes{margin-bottom:5px}
  .linha-regioes .tile{flex:0 0 calc(14.28% - 6px);min-height:0;padding:5px 4px}

  .titulo-secao{margin:10px 0 2px;font-size:1rem}

  /* A árvore começa em página nova: na versão anterior ela caía partida */

  /* Um gráfico por página, ocupando a folha inteira — antes eles eram
     espremidos lado a lado e os títulos ficavam truncados. */
  .graficos{display:block}
  /* duas colunas: gauge + Guaíba lado a lado; afluentes e chuva em linha
     cheia. Altura automática — travar em mm cortava o gráfico. */
  /* uma coluna: cada gráfico ocupa a largura útil da folha; dois por página */
  .graficos{break-before:page;page-break-before:always;display:block !important}
  .grafico{border:1px solid var(--borda);border-radius:8px;margin:0 0 4mm;
           padding:3px;height:auto;box-shadow:none;overflow:visible}
  /* dois gráficos por folha: 80mm cada + margens cabem nos 192mm úteis */
  .fig-claro,.fig-claro .js-plotly-plot,.fig-claro .plot-container,
  .fig-claro .svg-container{height:80mm !important}
  /* a barra de rolagem do modo claro aparecia impressa no PDF */
  .fig-claro{overflow:visible !important;max-width:none !important}
  /* NÃO usar width:!important aqui — sobrepõe o style inline que o
     Plotly.relayout escreve e o gráfico some da folha. */
  .grafico .js-plotly-plot,.grafico .plot-container{overflow:visible}

  .cartao-chuva{box-shadow:none;margin-top:8px}
  .valor-chuva{font-size:1.7rem}
  .rodape{margin-top:12px;padding-top:8px}
  .logo-rodape{height:34px;width:29px}
  .mini{font-size:.66rem}
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
function medidasDeImpressao(){
  // A largura quem resolve é o ResizeObserver do Plotly, ao entrar no layout
  // de impressão; a altura vem do CSS. Aqui só encolhemos títulos e margens,
  // que em 80mm de altura precisam de menos espaço.
  document.querySelectorAll('.fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,
      'title.font.size':13,'legend.font.size':10,
      'margin.l':55,'margin.r':55,'margin.t':44,'margin.b':36});}catch(e){}
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

    # status.json: arquivo minúsculo com a hora da coleta. O index.html é
    # pesado (assets embutidos) e fica em cache no CDN do GitHub Pages e no
    # navegador, então a página podia estar velha sem ninguém perceber. A
    # página consulta ESTE arquivo sem cache para saber a idade real do dado
    # e só se recarrega quando existe coleta nova de verdade.
    import json as _json
    (destino.parent / "status.json").write_text(_json.dumps({
        "timestamp_iso": snapshot.get("timestamp_iso", ""),
        "timestamp": snapshot.get("timestamp", ""),
        "estagio": (snapshot.get("classificacao") or {}).get("estagio", ""),
    }, ensure_ascii=False), encoding="utf-8")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, must-revalidate">
<title>Estágios Operacionais — Porto Alegre</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>{_CSS}</style>
<style>
  /* logo embutido uma única vez e reaproveitado nos dois lugares */
  .logo,.logo-rodape{{background-image:url("{_ativo_b64('cisc_logo.png','image/png')}");
     background-size:contain;background-repeat:no-repeat;background-position:center}}
  body::before{{background-image:linear-gradient(180deg,
      rgba(10,20,28,.42) 0%, var(--fundo) 78%), url("{_ativo_b64('guaiba.webp','image/webp')}")}}
  body.claro::before{{background-image:linear-gradient(180deg,
      rgba(238,242,246,.55) 0%, var(--fundo) 78%), url("{_ativo_b64('guaiba.webp','image/webp')}")}}
</style>
<script>{_JS_CEDO}</script>
</head>
<body class="{'claro' if tema == 'claro' else ''}">
<div class="wrap">
  <header class="cabecalho">
    <div class="logo" role="img" aria-label="CISC Porto Alegre"></div>
    <div class="titulos">
      <div class="sobretitulo">Porto Alegre/RS · Secretaria Municipal de Saúde</div>
      <h1>Plano de Contingência<span class="fina"> — Estágios Operacionais</span></h1>
      <div class="sub">Monitoramento automatizado · ANA · INMET · Poaclima ·
        Open-Meteo</div>
    </div>
  </header>
  <div class="acoes">
    <button id="btn-tema">☀ Modo claro</button>
    <button id="btn-print">🖨 Imprimir / PDF</button>
  </div>
  {_bloco_fontes(snapshot)}
  {_bloco_banner(snapshot)}
  {_bloco_avisos_inmet(snapshot)}
  {_bloco_cards(snapshot)}
  {_bloco_regioes(snapshot)}
  {_bloco_gatilhos(snapshot)}
  {_bloco_graficos(snapshot)}
  {_JS_FRESCOR}
  <div class="rodape">
    <div class="logo-rodape" role="img" aria-label="CISC Porto Alegre"></div>
    <div class="cisc">CISC Porto Alegre — Centro de Informações em Saúde e Clima</div>
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
