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
    """
    Escapa HTML e converte quebras de linha em <br>.

    Os itens alternativos das regras do Plano vinham separados por marcadores
    '•', o que sugeria uma lista de condições que valem TODAS ao mesmo tempo.
    No Plano essas condições são alternativas: basta uma. Agora a lógica
    entrega os itens já unidos por ' OU ' e aqui só damos destaque
    tipográfico ao conector, para ele ser lido como operador e não como
    parte da frase.
    """
    import html as _html
    if not txt:
        return ""
    seguro = _html.escape(str(txt)).replace("\n\n", "<br><br>").replace("\n", "<br>")
    seguro = seguro.replace(" OU ", " <span class='ou'>OU</span> ")
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
    def _rgb(hexa: str):
        h = hexa.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    def _rgba(hexa: str, alfa: float) -> str:
        r, g, b = _rgb(hexa)
        return f"rgba({r},{g},{b},{alfa})"

    def _luminancia(hexa: str) -> float:
        def canal(c):
            c /= 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = (canal(v) for v in _rgb(hexa))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def _legivel_no_escuro(hexa: str, alvo: float = 5.5) -> str:
        """
        Clareia a cor até alcançar contraste `alvo` sobre o fundo escuro.

        As cores dos estágios vêm do Plano e não podem mudar nas faixas
        preenchidas. Mas quando viram TEXTO sobre fundo escuro, as escuras
        somem: o roxo da CRISE tinha 2,5:1 e o vermelho da EMERGÊNCIA 3,4:1,
        contra o mínimo legível de 4,5:1. Aqui geramos só a variante de
        texto/borda, mantendo a matiz.
        """
        lum_fundo = _luminancia("#0A141C")
        r, g, b = _rgb(hexa)
        for passo in range(21):
            f = passo / 20
            atual = (round(r + (255 - r) * f), round(g + (255 - g) * f),
                     round(b + (255 - b) * f))
            hexa_atual = "#%02X%02X%02X" % atual
            razao = (_luminancia(hexa_atual) + 0.05) / (lum_fundo + 0.05)
            if razao >= alvo:
                return hexa_atual
        return "#FFFFFF"

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
            claro = _legivel_no_escuro(cor)
            # duas variáveis: o CSS escolhe conforme o tema (a clara só serve
            # sobre o fundo escuro; no modo claro a original é a legível)
            estilo = (f"--c:{cor};--c-esc:{claro};"
                      f"background:{_rgba(cor, .20 if i < idx_atual else .14)}")
        curto = "EMERGÊNCIA" if nome.startswith("SITUAÇÃO") else nome
        passos.append(f"<div class='{classe}' style='{estilo}'>"
                      f"<span class='grau'>{i + 1}</span>{curto}</div>")
    return f"<div class='trilho-estagios'>{''.join(passos)}</div>"


_TINTA_ESCURA = "#12202E"      # quase-preto azulado, do próprio tema claro


def _tom_suave(hexa: str, mistura: float = 0.45) -> str:
    """
    Clareia uma cor do Plano misturando-a com branco.

    As cores oficiais (laranja #F2830B, vermelho, roxo) são fortes de
    propósito: servem para a FAIXA do estágio, onde precisam gritar. Mas
    preencher blocos inteiros com elas cansa a vista e obriga a usar texto
    branco, que é o par de menor contraste possível sobre laranja saturado.

    Aqui a matiz é preservada e só a saturação cai, produzindo um tom pastel
    que aceita texto preto. A borda continua na cor cheia, então o bloco
    ainda se lê como "laranja = ALERTA" à distância.
    """
    h = (hexa or "#888888").lstrip("#")
    if len(h) != 6:
        return hexa
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return hexa
    m = max(0.0, min(1.0, mistura))
    return "#%02X%02X%02X" % tuple(round(c + (255 - c) * m) for c in (r, g, b))


def _linha_blocos(blocos: list, cor_linha: str, subtitulo: str,
                  nome: str | None = None) -> str:
    """Fileira BLOCO · E · BLOCO · E · BLOCO de um estágio."""
    if not blocos:
        return ""
    caixas = []
    for i, b in enumerate(blocos):
        classe = "no-arvore ativo" if b["ativo"] else "no-arvore inativo"
        estilo = (f"background:{_tom_suave(cor_linha)};"
                  f"border-color:{cor_linha};color:{_TINTA_ESCURA}"
                  if b["ativo"] else "")
        marca = "✔" if b["ativo"] else "✖"
        motivo = (b.get("motivo") or "").strip()
        # o motivo explica POR QUE o bloco está (ou não) ativo — sem ele
        # a árvore vira um "sim/não" sem auditoria
        html_motivo = (f"<span class='motivo-no'>{_texto_html(motivo)}</span>"
                       if motivo else "")
        dica = motivo.replace("\n", " · ").replace("'", "&#39;")
        # o OU do título também é operador da regra, e recebe o mesmo destaque
        titulo = str(b["titulo"]).replace(
            " OU ", " <span class='ou'>OU</span> ")
        caixas.append(
            f"<div class='{classe}' style='{estilo}' title='{dica}'>"
            f"<span class='marca'>{marca}</span>"
            f"<span class='rotulo'>{titulo}</span>"
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
        blocos, cor, "Todos os blocos precisam estar ativos")

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
      {corpo}{nota}{_complemento_inmet(snapshot)}
    </section>"""


def _cor_por_cota(chave: str, nivel: float, cota: float,
                  pct: float) -> tuple[str, str]:
    """
    Cor do card pelas COTAS da própria régua (Poaclima), não por % da cota
    de inundação. É o que o gráfico do Guaíba já fazia — antes o card
    pintava amarelo com 2,54 m (85% de 3,00 m) enquanto a linha laranja da
    cota de alerta, 2,50 m, já tinha sido cruzada no gráfico ao lado.

    Régua sem cota intermediária publicada (Gravataí não tem atenção) cai
    para as faixas de porcentagem antigas — inventar cota seria pior.
    """
    c = config.cotas_do_card(chave)
    atencao, alerta = c.get("atencao"), c.get("alerta")

    if nivel >= cota:
        return config.CORES_ESTAGIOS["SITUAÇÃO DE EMERGÊNCIA"], "acima da cota de inundação"
    if alerta is not None and nivel >= alerta:
        return config.CORES_ESTAGIOS["ALERTA"], f"acima da cota de alerta ({alerta:.2f} m)"
    if atencao is not None and nivel >= atencao:
        return config.CORES_ESTAGIOS["MOBILIZAÇÃO"], f"acima da cota de atenção ({atencao:.2f} m)"
    if atencao is None and alerta is None:
        # sem cotas publicadas: mantém o comportamento antigo, por faixa
        if pct >= 85:
            return config.CORES_ESTAGIOS["ALERTA"], ""
        if pct >= 65:
            return config.CORES_ESTAGIOS["MOBILIZAÇÃO"], ""
    if atencao is None and pct >= 65:
        return config.CORES_ESTAGIOS["MOBILIZAÇÃO"], ""
    return config.CORES_ESTAGIOS["NORMALIDADE"], ""


def _bloco_cards(snapshot: dict) -> str:
    ind = snapshot.get("indicadores") or {}
    # Quando a ANA está fora, o nível do Guaíba vem do Poaclima (mesma
    # régua do Cais Mauá). O card precisa DIZER isso: um número certo com
    # a fonte errada é pior que um número ausente, porque parece auditado.
    fonte_guaiba = snapshot.get("fonte_nivel_guaiba")
    cards = []
    for info in config.INFO_RIOS_CARDS:
        nivel = componentes._nivel_do_indicador(ind, info["chave"])
        cota = info["cota_inundacao"]
        estacao = info["estacao"]
        if info["chave"] == "Guaiba_PortoAlegre_CaisMaua" and fonte_guaiba:
            estacao = fonte_guaiba

        if nivel is not None and cota:
            pct = max(0.0, nivel / cota * 100.0)
            cor, situacao = _cor_por_cota(info["chave"], nivel, cota, pct)
            valor = (f"<div class='valor' style='color:{cor}'>{nivel:.2f} m"
                     f"<span class='cota'> / {cota:.2f} m</span></div>")
            barra = (f"<div class='trilho'><div class='barra' style='width:"
                     f"{min(pct, 100):.0f}%;background:{cor}'></div></div>")
            rodape = (f"<div class='pct'>{pct:.0f}% da cota de inundação"
                      f"{' · ' + situacao if situacao else ''}</div>")
        else:
            texto = f"{nivel:.2f} m" if nivel is not None else "—"
            valor = f"<div class='valor neutro'>{texto}</div>"
            barra = ""
            rodape = ("<div class='pct'>cota de inundação: não informada</div>"
                      if nivel is not None else "<div class='pct'>sem leitura</div>")

        cards.append(f"""
        <div class="card">
          <div class="rio">{info['rotulo']}</div>
          <div class="est">{info['municipio']} · est. {estacao}</div>
          {valor}{barra}{rodape}
        </div>""")
    return f"<section class='cards'>{''.join(cards)}</section>"


def _bloco_regioes(snapshot: dict) -> str:
    alertas = (snapshot.get("indicadores") or {}).get("alertas_regionais") or []
    # Distinção que faltava: região sem MARCADOR no mapa não é região sem
    # dado — é região sem alerta. "Sem dado" só se o Poaclima não respondeu.
    fontes = snapshot.get("fontes") or {}
    # Só a camada de ALERTAS decide entre "sem alerta" e "sem dado" —
    # os níveis do Guaíba não dizem nada sobre risco por região.
    poaclima_ok = bool(fontes.get("Poaclima · alertas",
                                  fontes.get("Poaclima", False)))
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
        # Faixa cheia só no topo: o corpo pastel mantém a leitura confortável
        # e a tarja devolve a cor forte do risco, que é o que se enxerga de
        # longe ao bater o olho na grade das 17 regiões.
        return (f"<div class='tile' style='background:{_tom_suave(cor)};"
                f"border:1px solid {cor};border-top:6px solid {cor};"
                f"color:{_TINTA_ESCURA}'>"
                f"<div class='num'>{num}</div><div class='nome'>{nome}</div>"
                f"<div class='status'>{status}</div>"
                f"<div class='detalhe'>{detalhe}</div></div>")

    # Tela: triângulo 8 / 6 / 3
    # Impressão: 6 / 6 / 5. A divisão anterior era 7 / 6 / 4, mas as sete
    # células da primeira linha não cabiam na largura útil da A4 e a sétima
    # quebrava sozinha — o PDF saía 6 / 1 / 6 / 4, com uma linha órfã. Com
    # seis por linha as três fileiras ficam equilibradas e nada quebra.
    def grade(faixas):
        return "".join(
            f"<div class='linha-regioes'>{''.join(tile(n) for n in faixa)}</div>"
            for faixa in faixas)

    html_linhas = (f"<div class='regioes-tela'>{grade([range(1, 9), range(9, 15), range(15, 18)])}</div>"
                   f"<div class='regioes-print'>{grade([range(1, 7), range(7, 13), range(13, 18)])}</div>")

    return f"""
    <section class="bloco-regioes">
      <h3 class="titulo-secao">Risco por região — Defesa Civil (Poaclima)</h3>
      <div class="sub">Status capturado dos marcadores do mapa oficial ·
        cinza = {"região sem alerta vigente" if poaclima_ok
                 else "Poaclima não respondeu nesta coleta"}</div>
      <div class="regioes">{html_linhas}</div>
    </section>"""


def _data_br(bruto) -> str:
    """
    Converte a data de um aviso para 'dd/mm/aaaa HH:MM'.

    O INMET entrega a data em formatos diferentes conforme o campo: ISO com
    'Z' ('2026-07-31T00:00:00.000Z'), ISO sem fuso, ou já no padrão
    brasileiro. Jogar o texto cru na tela — como estava — é despejar detalhe
    de máquina em cima de quem precisa decidir. Quando o horário é 00:00 e
    veio só a data, mostramos só a data: fingir precisão de minuto num dado
    que não a tem é pior que omitir.
    """
    if not bruto:
        return ""
    txt = str(bruto).strip()
    import datetime as _dt
    formatos = ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y")
    for f in formatos:
        try:
            d = _dt.datetime.strptime(txt, f)
        except ValueError:
            continue
        so_data = f.endswith("%Y-%m-%d") or f.endswith("%d/%m/%Y")
        if so_data or (d.hour == 0 and d.minute == 0):
            return d.strftime("%d/%m/%Y")
        return d.strftime("%d/%m/%Y %H:%M")
    return txt


def _periodo_aviso(a: dict) -> str:
    """
    Período do aviso em uma linha.

    Quando começa e termina no mesmo dia — o caso mais comum — a data
    aparece uma vez só, com as horas: 'em 29/07/2026, das 00:00 às 23:59'.
    Repetir a data dos dois lados enche a linha sem informar nada.
    """
    import datetime as _dt

    def _dt_de(bruto):
        if not bruto:
            return None
        for f in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S.%fZ",
                  "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                  "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                return _dt.datetime.strptime(str(bruto).strip(), f)
            except ValueError:
                continue
        return None

    di, df = _dt_de(a.get("inicio")), _dt_de(a.get("fim"))
    if di and df and di.date() == df.date():
        return (f"em {di:%d/%m/%Y}, das {di:%H:%M} às {df:%H:%M}"
                if (di.hour, di.minute) != (df.hour, df.minute)
                else f"em {di:%d/%m/%Y}")

    ini, fim = _data_br(a.get("inicio")), _data_br(a.get("fim"))
    if ini and fim and ini != fim:
        return f"de {ini} até {fim}"
    if fim and not ini:
        return f"até {fim}"
    return f"em {ini}" if ini else ""


def _bloco_avisos_defesa_civil(snapshot: dict) -> str:
    """
    NÃO ESTÁ MONTADO NO PAINEL. Saiu a pedido da chefia: a página de avisos
    da prefeitura fica meses sem publicação, e um bloco de alertas parado é
    pior do que bloco nenhum — quem lê não sabe se o silêncio é calmaria ou
    desatualização. A coleta segue rodando e o dado continua no snapshot;
    para trazer de volta, é uma linha na montagem da página.

    Retângulo de destaque: avisos publicados pela DEFESA CIVIL DE POA.

    Tomou o lugar do bloco do INMET no topo. O INMET compõe a análise, mas
    deixou de ser fonte principal desde 2025, e manter os dois em destaque
    colocava duas escalas de cor para o mesmo céu — divergência que, num
    painel de contingência, vira dúvida na hora de decidir. O do INMET
    agora aparece como complemento, junto do banner de estágio.
    """
    av = snapshot.get("avisos_defesa_civil") or {}
    vigentes = av.get("vigentes") or []
    ultimo = av.get("ultimo")
    url_fonte = av.get("url") or "https://prefeitura.poa.br/defesa-civil/avisos-e-alertas"

    if not av.get("consultado"):
        return ("<section class='avisos-dc indisponivel'>"
                "<div class='titulo-aviso'>Avisos da Defesa Civil de Porto "
                "Alegre</div><div class='texto-aviso'>Não foi possível "
                "consultar a página de avisos nesta atualização — verifique "
                f"em <a href='{url_fonte}' target='_blank' "
                "rel='noopener'>prefeitura.poa.br/defesa-civil</a></div>"
                "</section>")

    # Página respondeu, mas nenhum aviso foi interpretado: a página sempre
    # teve dezenas deles, então isso é leitura quebrada, não ano calmo.
    # Anunciar "nenhum aviso vigente" aqui seria transformar uma falha de
    # coleta em atestado de tranquilidade.
    if not av.get("estrutura_ok", True):
        return ("<section class='avisos-dc indisponivel'>"
                "<div class='titulo-aviso'>Avisos da Defesa Civil de Porto "
                "Alegre</div><div class='texto-aviso'>A página respondeu, mas "
                "<b>não foi possível interpretar a lista de avisos</b> nesta "
                "atualização — consulte direto em "
                f"<a href='{url_fonte}' target='_blank' rel='noopener'>"
                "prefeitura.poa.br/defesa-civil</a></div></section>")

    if not vigentes:
        # Dia sem aviso é informação: dizer isso, e dizer QUANDO foi o
        # último, é o que separa "nada acontecendo" de "ninguém olhou".
        historico = ""
        if ultimo:
            historico = (
                "<div class='ultimo-aviso'>Último aviso publicado: "
                f"<a href='{ultimo.get('url', url_fonte)}' target='_blank' "
                f"rel='noopener'>{_texto_html(ultimo.get('titulo', 'aviso'))}"
                f"</a> · {ultimo.get('data_br', '—')}</div>")
        return (f"<section class='avisos-dc sem-aviso'>"
                f"<div class='titulo-aviso'>Avisos da Defesa Civil de Porto "
                f"Alegre</div><div class='texto-aviso'><b>Nenhum aviso "
                f"vigente</b> para Porto Alegre no momento.</div>"
                f"{historico}</section>")

    itens = []
    for a in vigentes[:4]:
        cor_nome = (a.get("cor_declarada") or "").lower()
        cor = {"vermelho": "#CE1B22", "vermelha": "#CE1B22",
               "laranja": "#F2830B",
               "amarelo": "#E3B505", "amarela": "#E3B505"}.get(cor_nome)
        # Sem cor declarada no texto, nenhum chip de severidade: atribuir
        # uma cor que a Defesa Civil não publicou seria inventar gravidade.
        chip = (f"<span class='sev' style='background:{cor}'>"
                f"{cor_nome.capitalize()}</span>" if cor else "")
        borda = cor or "#5B9BF3"
        itens.append(
            f"<div class='item-aviso' style='border-left:6px solid {borda}'>"
            f"{chip}<span class='desc'>"
            f"<a href='{a.get('url', url_fonte)}' target='_blank' "
            f"rel='noopener'>{_texto_html(str(a.get('titulo', ''))[:160])}</a>"
            f"</span><div class='periodo'>publicado em "
            f"{a.get('data_br', '—')}</div></div>")

    return (f"<section class='avisos-dc'>"
            f"<div class='titulo-aviso'>Avisos vigentes — Defesa Civil de "
            f"Porto Alegre ({len(vigentes)})</div>{''.join(itens)}</section>")


def _complemento_inmet(snapshot: dict) -> str:
    """
    Linha discreta com os avisos do INMET, dentro do banner de estágio.

    Regra combinada com o CISC: aparece quando há aviso; some quando não há
    e o estágio não é normalidade (nesse caso a atenção pertence aos blocos
    do Plano, não a uma linha que diz "nada"); e em normalidade sem aviso
    diz explicitamente "sem avisos do INMET", porque num dia calmo a
    ausência confirmada vale mais do que o silêncio.
    """
    av = snapshot.get("avisos_inmet") or {}
    alertas = av.get("alertas") or []
    estagio = (snapshot.get("classificacao") or {}).get("estagio", "")
    normalidade = str(estagio).upper().startswith("NORMAL")

    if not av.get("consultado", True):
        return ("<div class='compl-inmet'><span class='rot-compl'>INMET</span>"
                "<span class='txt-compl'>não foi possível consultar os avisos "
                "nesta atualização</span></div>")

    if not alertas:
        if not normalidade:
            return ""
        return ("<div class='compl-inmet'><span class='rot-compl'>INMET</span>"
                "<span class='txt-compl'>sem avisos do INMET para Porto "
                "Alegre</span></div>")

    partes = []
    for a in alertas[:3]:
        sev = a.get("severidade") or "Amarelo"
        cor = config.CORES_AVISO_INMET.get(sev, "#E3B505")
        tipo = (a.get("tipo") or a.get("descricao") or "aviso").strip()
        periodo = _periodo_aviso(a)
        partes.append(
            f"<span class='chip-inmet' style='border-color:{cor}'>"
            f"<i style='background:{cor}'></i>"
            f"{_texto_html(tipo[:70])}"
            + (f" <small>{periodo}</small>" if periodo else "")
            + "</span>")
    return (f"<div class='compl-inmet'><span class='rot-compl'>INMET</span>"
            f"<span class='txt-compl'>complemento à análise:</span>"
            f"{''.join(partes)}</div>")


def _bloco_avisos_inmet(snapshot: dict) -> str:
    """
    NÃO ESTÁ MONTADO NO PAINEL. Era o retângulo de destaque no topo e deu
    lugar aos avisos da Defesa Civil de POA (_bloco_avisos_defesa_civil);
    o INMET agora entra como complemento no banner (_complemento_inmet).
    Mantido porque continua correto e é uma linha para voltar, se o CISC
    decidir que quer os dois em destaque.

    Retângulo com os avisos meteorológicos vigentes do INMET para POA.
    """
    av = snapshot.get("avisos_inmet") or {}
    alertas = av.get("alertas") or []

    if not av.get("consultado", True):
        return ("<section class='avisos-inmet indisponivel'>"
                "<div class='titulo-aviso'>Avisos do INMET</div>"
                "<div class='texto-aviso'>Não foi possível consultar o INMET "
                "nesta atualização — verifique em avisos.inmet.gov.br</div>"
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
        # o título é o TIPO do evento (Vendaval, Tempestade); a descrição
        # detalhada — intensidade e riscos — vai abaixo, que é a informação
        # que diz o que fazer com o aviso
        tipo = (a.get("tipo") or a.get("descricao") or "").strip()
        detalhe = (a.get("detalhe") or "").strip()
        # Defesa em profundidade: mesmo com o filtro na coleta, o painel não
        # imprime um data URI nem um blob sem espaços. Já aconteceu de um
        # PNG em base64 vazar para cá; uma linha de guarda custa menos que
        # a próxima captura de tela constrangedora.
        if (detalhe == tipo or detalhe.lower().startswith("data:")
                or "base64" in detalhe.lower() or detalhe.count(" ") < 4):
            detalhe = ""
        periodo = _periodo_aviso(a)
        itens.append(
            f"<div class='item-aviso' style='border-left:6px solid {cor}'>"
            f"<span class='sev' style='background:{cor}'>{sev}</span>"
            f"<span class='desc'>{_texto_html(tipo[:120])}</span>"
            + (f"<div class='detalhe-aviso'>{_texto_html(detalhe[:400])}</div>"
               if detalhe else "")
            + (f"<div class='periodo'>{periodo}</div>" if periodo else "")
            + "</div>")
    return (f"<section class='avisos-inmet'>"
            f"<div class='titulo-aviso'>Avisos meteorológicos vigentes — INMET"
            f" ({len(alertas)})</div>{''.join(itens)}</section>")


# ──────────────────────────────────────────────────────────────────────────
# Previsão do tempo — 5 dias (Poaclima/Catavento)
# ──────────────────────────────────────────────────────────────────────────
# A escala de chuva usa as MESMAS cores do Plano de Contingência: quem lê o
# painel já aprendeu que verde/amarelo/laranja/vermelho significam gravidade
# crescente. Inventar uma segunda paleta para a chuva obrigaria a decorar
# duas gramáticas de cor na mesma tela.
_ESCALA_CHUVA = (
    (0.05, "#8FA3B4", "sem chuva prevista"),
    (10.0, "#3FA9F5", "chuva fraca"),
    (30.0, "#E3B505", "chuva moderada"),
    (50.0, "#F2830B", "chuva forte"),
    (float("inf"), "#CE1B22", "chuva muito forte"),
)

# Sigla → (nome falado, graus de ONDE o vento vem). A seta desenhada aponta
# para onde o vento SOPRA (graus + 180), que é como a Defesa Civil lê o
# arraste de chuva sobre a cidade.
_DIR_VENTO = {
    "N": ("norte", 0), "NE": ("nordeste", 45),
    "L": ("leste", 90), "E": ("leste", 90),
    "SE": ("sudeste", 135), "S": ("sul", 180), "SO": ("sudoeste", 225),
    "O": ("oeste", 270), "W": ("oeste", 270), "NO": ("noroeste", 315),
}

_DIAS_SEMANA = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def _cor_chuva(mm: float | None) -> tuple[str, str]:
    """Cor e rótulo da faixa de chuva prevista para o dia."""
    if mm is None:
        return "#8FA3B4", "sem dado"
    for limite, cor, rotulo in _ESCALA_CHUVA:
        if mm < limite:
            return cor, rotulo
    return "#CE1B22", "chuva muito forte"


def _icone_tempo(descricao: str | None, mm: float | None) -> str:
    """
    Ícone SVG embutido para a condição do dia.

    SVG inline em vez de fonte de ícones ou PNG: a página é autocontida
    (assets em base64) e precisa imprimir em PDF sem requisição externa —
    ícone que depende da rede é ícone que falta na folha impressa.
    """
    d = (descricao or "").lower()
    chuva = mm or 0.0

    sol = ("<circle cx='11' cy='11' r='5.4' fill='#F7B733'/>"
           "<g stroke='#F7B733' stroke-width='2' stroke-linecap='round'>"
           "<path d='M11 1.6v2.6M11 17.8v2.6M1.6 11h2.6M17.8 11h2.6"
           "M4.3 4.3l1.9 1.9M15.8 15.8l1.9 1.9M17.7 4.3l-1.9 1.9"
           "M6.2 15.8l-1.9 1.9'/></g>")
    sol_canto = ("<circle cx='22.5' cy='9' r='4.6' fill='#F7B733'/>"
                 "<g stroke='#F7B733' stroke-width='1.8' stroke-linecap='round'>"
                 "<path d='M22.5 1.6v2.2M29.4 9h-2.2M27.4 4.1l-1.6 1.6"
                 "M27.4 13.9l-1.6-1.6'/></g>")
    nuvem = ("<g fill='#A9BED2'><circle cx='12' cy='20' r='5.4'/>"
             "<circle cx='19.6' cy='18' r='7'/>"
             "<rect x='9.4' y='19.6' width='13' height='5.6' rx='2.8'/></g>")
    nuvem_escura = nuvem.replace("#A9BED2", "#7E93A8")
    gotas = ("<g stroke='#4FA3E3' stroke-width='2.2' stroke-linecap='round'>"
             "<path d='M12 26.6v3.2M17 26.6v3.6M22 26.6v3.2'/></g>")
    raio = ("<path d='M17.6 25.2h4.2l-2.4 3.4h3l-6.2 5.2 1.8-4.6h-2.6z'"
            " fill='#F5C518' stroke='#F5C518' stroke-width='.6'/>")
    neblina = ("<g stroke='#A9BED2' stroke-width='2.2' stroke-linecap='round'>"
               "<path d='M6 22h20M9 27h16'/></g>")

    if "trovoada" in d or "raio" in d or "tempestade" in d:
        corpo, titulo = nuvem_escura + raio, descricao or "trovoadas"
    elif "nevoeiro" in d or "névoa" in d or "nevoa" in d or "neblina" in d:
        corpo, titulo = nuvem + neblina, descricao or "nevoeiro"
    elif ("sol" in d or "claro" in d) and ("chuva" in d or "pancada" in d):
        corpo, titulo = sol_canto + nuvem + gotas, descricao or "pancadas de chuva"
    elif "sol" in d and ("nuvem" in d or "nuvens" in d or "parcial" in d):
        corpo, titulo = sol_canto + nuvem, descricao or "sol entre nuvens"
    elif "chuva" in d or "chuvisco" in d or "garoa" in d or "pancada" in d:
        corpo, titulo = nuvem_escura + gotas, descricao or "chuva"
    elif "encoberto" in d or "nublado" in d or "nuvens" in d:
        corpo, titulo = nuvem, descricao or "nublado"
    elif "sol" in d or "claro" in d or "limpo" in d:
        corpo, titulo = sol, descricao or "sol"
    elif chuva >= 0.5:
        corpo, titulo = nuvem_escura + gotas, descricao or "chuva"
    else:
        corpo, titulo = nuvem, descricao or "condição não informada"

    import html as _html
    return (f"<svg class='ic-tempo' viewBox='0 0 34 34' role='img' "
            f"aria-label='{_html.escape(titulo)}'>{corpo}</svg>")


def _regua_chuva(mm: float | None, teto: float, cor: str) -> str:
    """
    Régua vertical da chuva prevista.

    A barra horizontal já é a linguagem dos cards de rio (nível × cota).
    Para a chuva usamos a régua em pé — o instrumento do assunto — e a
    escala é COMPARTILHADA pelos cinco dias, para a altura da água poder
    ser comparada de um cartão para o outro sem reler os números.
    """
    if mm is None:
        return ("<div class='regua-chuva' title='sem dado'>"
                "<span class='marca' style='bottom:50%'></span></div>")
    altura = 0 if mm <= 0 else max(6.0, min(100.0, mm / teto * 100.0))
    return (f"<div class='regua-chuva' title='{mm:.0f} mm de {teto:.0f} mm "
            f"(maior valor da semana)'>"
            f"<span class='marca' style='bottom:50%'></span>"
            f"<span class='agua' style='height:{altura:.0f}%;background:{cor}'></span>"
            f"</div>")


def _rotulo_dia(data, hoje) -> tuple[str, str]:
    """('HOJE'|'AMANHÃ'|'QUI', '31/07') — o dia como as pessoas o chamam."""
    delta = (data.date() - hoje.date()).days
    if delta == 0:
        nome = "hoje"
    elif delta == 1:
        nome = "amanhã"
    else:
        nome = _DIAS_SEMANA[data.weekday()]
    return nome.upper(), data.strftime("%d/%m")


def _bloco_previsao(snapshot: dict, quantos: int = 5) -> str:
    """
    Cinco cartões de previsão — a tabela da Catavento no Poaclima, lida em
    formato de cartão: um dia por cartão, com chuva, temperatura, umidade e
    vento. É a mesma previsão que a Defesa Civil de POA usa.
    """
    import datetime as _dt

    dias_brutos = snapshot.get("previsao_poaclima") or []
    atualizado = snapshot.get("previsao_atualizada_em")
    hoje = _dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    dias = []
    for d in dias_brutos:
        data = None
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                data = _dt.datetime.strptime(str(d.get("data", ""))[:19], f)
                break
            except ValueError:
                continue
        if data and data >= hoje:
            dias.append((data, d))
    dias.sort(key=lambda p: p[0])
    dias = dias[:quantos]

    if not dias:
        # Fonte fora do ar é informação, não motivo para esconder a seção:
        # quem decide precisa saber que a previsão da Catavento faltou.
        return ("""
    <h3 class="titulo-secao">Previsão do tempo — 5 dias</h3>
    <section class="previsao-vazia">Previsão do Poaclima/Catavento
      indisponível nesta coleta. Os gráficos de chuva seguem com a fonte
      de reserva (Open-Meteo).</section>""")

    teto = max([(d.get("precipitacao_total_mm") or 0.0) for _, d in dias] + [10.0])

    cartoes = []
    for data, d in dias:
        mm = d.get("precipitacao_total_mm")
        cor, faixa = _cor_chuva(mm)
        rot_dia, data_br = _rotulo_dia(data, hoje)
        e_hoje = data.date() == hoje.date()

        tmax, tmin = d.get("temp_max_c"), d.get("temp_min_c")
        temp = (f"<b class='t-max'>{tmax}°</b>"
                f"<span class='barra-temp'>/</span>"
                f"<b class='t-min'>{tmin}°</b>") if tmax is not None and tmin is not None \
            else (f"<b class='t-max'>{tmax}°</b>" if tmax is not None else "—")

        umax, umin = d.get("umidade_max_pct"), d.get("umidade_min_pct")
        umid = (f"{umin}–{umax}%" if umin is not None and umax is not None
                else (f"{umax}%" if umax is not None else "—"))

        vento_kmh = d.get("vento_kmh")
        sigla = (d.get("dir_vento") or "").upper()
        nome_dir, graus = _DIR_VENTO.get(sigla, ("", None))
        if vento_kmh is None:
            vento = "—"
        else:
            seta = ""
            if graus is not None:
                seta = (f"<span class='seta-vento' aria-hidden='true' "
                        f"style='transform:rotate({(graus + 180) % 360}deg)'>↑</span>")
            rotulo_dir = (f"<span class='sigla-vento' title='vento de {nome_dir}'>"
                          f"{sigla}</span>" if sigla else "")
            vento = f"{vento_kmh} <small>km/h</small> {seta}{rotulo_dir}"

        mm_txt = (f"{mm:.0f}" if mm is not None else "—")
        cartoes.append(f"""
        <article class="dia-prev{' hoje' if e_hoje else ''}">
          <header class="topo-prev">
            <span class="rot-dia">{rot_dia}</span>
            <span class="data-dia">{data_br}</span>
          </header>
          <div class="corpo-prev">
            {_icone_tempo(d.get('descricao'), mm)}
            <div class="chuva-prev">
              <div class="mm-prev" style="color:{cor}">{mm_txt}<small>mm</small></div>
              <div class="rot-chuva">{faixa}</div>
            </div>
            {_regua_chuva(mm, teto, cor)}
          </div>
          <div class="desc-prev">{_texto_html(d.get('descricao') or '—')}</div>
          <ul class="metricas-prev">
            <li><span class="rot">Máx / mín</span><span class="val">{temp}</span></li>
            <li><span class="rot">Umidade</span><span class="val">{umid}</span></li>
            <li><span class="rot">Vento</span><span class="val">{vento}</span></li>
          </ul>
        </article>""")

    fonte = ("Fonte: Poaclima / Catavento Meteorologia e Meio Ambiente"
             + (f" · boletim de {atualizado}" if atualizado else ""))
    return f"""
    <h3 class="titulo-secao">Previsão do tempo — próximos {len(dias)} dias</h3>
    <div class="fonte-prev">{fonte}</div>
    <section class="previsao">{''.join(cartoes)}</section>"""


# A seção "Gatilhos de campo confirmados" foi retirada do corpo da página.
# Ela repetia, no meio do painel, uma informação que já aparece onde ela de
# fato significa alguma coisa: dentro do 3º bloco do banner ("Famílias
# deixando casas OU demanda por abrigo OU bloqueio de vias OU demanda na
# saúde"), listada como a evidência que ativa aquele bloco. Solta no meio da
# página, a lista sugeria um peso próprio que os gatilhos não têm — eles são
# uma das alternativas de UM bloco, não um veredito. Quem monta o painel edita
# o gatilhos_manuais.txt; quem lê o painel precisa é do estágio e do porquê.


def _figura_dupla(constroi, altura_css: str) -> str:
    """
    Renderiza a MESMA figura nos dois temas e devolve os dois blocos.

    O CSS decide qual aparece. É desperdício de bytes e economia de dor de
    cabeça: alternar tema sem recarregar exigiria redesenhar o Plotly, e
    figura redesenhada fora da tela sai em branco no PDF.
    """
    blocos = []
    for tema in ("dark", "claro"):
        fig = constroi(tema)
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", autosize=True)
        html_fig = fig.to_html(
            full_html=False,
            # o cabeçalho é o primeiro Plotly da página: é ele que carrega a lib
            include_plotlyjs="cdn" if tema == "dark" and not _figura_dupla.carregado else False,
            config={"displayModeBar": False, "responsive": True},
            default_width="100%", default_height=altura_css)
        if tema == "dark":
            _figura_dupla.carregado = True
        blocos.append(f"<div class='fig-{tema}'>{html_fig}</div>")
    return "".join(blocos)


_figura_dupla.carregado = False


def _bloco_cabecalho(snapshot: dict) -> str:
    """
    Cabeçalho: identidade à esquerda, velocímetro do estágio à direita.

    O estágio operacional é a resposta que a página existe para dar. Ele
    estava no meio dos gráficos, abaixo de dois rolamentos de tela — quem
    abria o painel no celular via logo, título e cards antes de descobrir
    em que estágio a cidade está. Subiu para a primeira dobra, em tamanho
    reduzido, ao lado do título.
    """
    _figura_dupla.carregado = False   # nova página, nova contagem
    gauge = _figura_dupla(
        lambda t: componentes.gauge_estagio(
            snapshot.get("classificacao") or {}, t, compacto=True), "215px")
    return f"""
  <header class="cabecalho">
    <div class="identidade">
      <div class="logo" role="img" aria-label="CISC Porto Alegre"></div>
      <div class="titulos">
        <div class="sobretitulo">Porto Alegre/RS · Secretaria Municipal de Saúde</div>
        <h1>Plano de Contingência<span class="fina"> — Estágios Operacionais</span></h1>
        <div class="sub">Monitoramento automatizado · ANA · INMET · Poaclima ·
          Open-Meteo</div>
        <div class="acoes">
          <button id="btn-tema">☀ Modo claro</button>
          <button id="btn-print">🖨 Imprimir / PDF</button>
        </div>
      </div>
    </div>
    <div class="gauge-cabecalho">{gauge}</div>
  </header>"""


def _bloco_graficos(snapshot: dict) -> str:
    """
    Cada gráfico é renderizado DUAS vezes (tema escuro e claro). O CSS mostra
    a versão certa conforme o tema — e na impressão força sempre a clara,
    senão o texto dos gráficos sai cinza-claro sobre papel branco.

    O velocímetro saiu daqui: agora mora no cabeçalho.
    """
    construtores = [
        # (constrói, largura_print, altura_print, ocupa_linha_inteira)
        # a MESMA previsão usada no gráfico de afluentes, para os dois
        # gráficos nunca discordarem sobre o mesmo Cais Mauá
        (lambda t: componentes.grafico_guaiba(
            snapshot.get("serie_guaiba", []), t,
            previsao=(snapshot.get("series_afluentes") or {}).get(
                "__previsao_guaiba__")), 1040, 268, True),
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

    # a biblioteca do Plotly já veio com o velocímetro do cabeçalho
    partes, primeiro = [], not _figura_dupla.carregado
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
            + _bloco_previsao(snapshot))


def _rodape_chuva(snapshot: dict) -> str:
    """
    NÃO ESTÁ MONTADO NO PAINEL. Ficava no rodapé, depois dos gráficos, e deu
    lugar aos cinco cartões de previsão (_bloco_previsao). A função segue aqui
    porque o número da CHUVA OBSERVADA que ela mostrava não aparece em nenhum
    outro lugar em forma de número — para trazê-la de volta, basta somá-la ao
    retorno de _bloco_graficos.

    Card de chuva: 5 dias para trás × 5 dias para frente, lado a lado.

    As cores dos números espelham as do gráfico de precipitação — laranja
    para o acumulado observado, magenta para a previsão do Poaclima — para
    que o leitor ligue o número à linha correspondente sem legenda.

    Nada de metainformação de coleta aqui: quantas fontes foram testadas
    é assunto de depuração e vive no CSV e no log, não no painel público.
    """
    # Janela de 3 dias dos dois lados (antes eram 5). Três dias é o horizonte
    # em que a previsão do Poaclima ainda é confiável e em que a chuva já
    # caída ainda explica o nível dos rios de hoje.
    obs = snapshot.get("chuva_obs_3d_mm", snapshot.get("chuva_obs_5d_mm"))
    prev = snapshot.get("chuva_prev_3d_mm", snapshot.get("chuva_prev_5d_mm"))
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
      {coluna("CHUVA OBSERVADA", fonte_obs, obs, "últimos 3 dias", "#F2830B")}
      <div class="divisor-chuva"></div>
      {coluna("CHUVA PREVISTA", fonte_prev, prev, "próximos 3 dias", "#E5399B")}
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
/* Cabeçalho em duas colunas: identidade à esquerda, estágio à direita.
   Em telas estreitas as duas viram linhas empilhadas. */
.cabecalho{display:flex;align-items:center;justify-content:space-between;
     gap:18px;text-align:left;margin-bottom:10px;flex-wrap:wrap}
.identidade{display:flex;align-items:center;gap:16px;
     flex:1 1 440px;min-width:0}
.gauge-cabecalho{flex:0 1 480px;min-width:290px;max-width:540px;
     align-self:center}
@media(max-width:820px){.identidade,.gauge-cabecalho{flex:1 1 100%;max-width:none}
  .cabecalho{justify-content:center}}
.logo{height:70px;width:59px;flex:0 0 auto}
.sobretitulo{font-family:"Barlow Condensed",sans-serif;font-weight:600;
     font-size:.95rem;letter-spacing:.14em;text-transform:uppercase;
     color:var(--cisc)}
h1{font-family:"Barlow Condensed","Arial Narrow",sans-serif;font-weight:700;
     font-size:2.45rem;line-height:1.05;margin:2px 0 4px;letter-spacing:.01em}
h1 .fina{font-weight:500;color:var(--txt2)}
.sub{color:var(--txt2);font-size:.98rem;margin-bottom:0}
.acoes{margin:12px 0 0}
button{background:transparent;color:var(--txt);border:1px solid var(--borda);
       border-radius:8px;padding:8px 16px;font-size:.92rem;cursor:pointer;
       margin:0 6px 0 0;font-family:inherit;transition:background .15s}
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
.passo.antes,.passo.depois{color:var(--c-esc);border-color:var(--c-esc)}
body.claro .passo.antes,body.claro .passo.depois{color:var(--c);
  border-color:var(--c)}
.passo.antes{opacity:1}
.passo.depois{opacity:.92}
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
.tile{border-radius:10px;padding:8px 6px;min-height:74px}
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
.item-aviso .detalhe-aviso{font-size:.84rem;color:var(--txt);opacity:.9;
  margin-top:4px;line-height:1.35}
/* rede de segurança de layout: nenhum token comprido pode esticar o
   cartão para fora da página, aconteça o que acontecer na origem */
.item-aviso .desc,.item-aviso .detalhe-aviso{overflow-wrap:anywhere;
  word-break:break-word}
.item-aviso .periodo{font-size:.78rem;color:var(--txt2);margin-top:3px}

/* ── Avisos da Defesa Civil de POA (bloco de destaque) ───────────────
   Herda a caixa do antigo bloco do INMET de propósito: para quem lê o
   painel todo dia, o aviso continua no mesmo lugar e com a mesma forma —
   só a origem mudou, e ela está escrita no título. */
.avisos-dc{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:10px 14px;margin-bottom:16px;text-align:left}
.avisos-dc.sem-aviso{border-color:#2E9E44}
.avisos-dc.indisponivel{border-color:#8B95A1}
.avisos-dc.sem-aviso .texto-aviso{color:var(--txt)}
.avisos-dc .item-aviso .desc a{color:var(--txt);text-decoration:none;
  border-bottom:1px dotted var(--txt2)}
.avisos-dc .item-aviso .desc a:hover{border-bottom-style:solid}
.ultimo-aviso{text-align:center;font-size:.82rem;color:var(--txt2);
  margin-top:6px}
.ultimo-aviso a{color:var(--txt2)}

/* ── Complemento do INMET, dentro do banner de estágio ───────────────
   Discreto por decisão: o INMET compõe a análise, não a comanda. Fica na
   base do banner, com tipografia menor que a dos blocos do Plano, para
   ler-se como nota de rodapé da decisão — e não como uma segunda decisão. */
.compl-inmet{display:flex;flex-wrap:wrap;align-items:center;gap:6px;
  margin:10px 12px 2px;padding-top:8px;
  border-top:1px dashed var(--borda-fina);font-size:.82rem}
.rot-compl{font-family:"Barlow Condensed",sans-serif;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-size:.76rem;
  color:var(--txt2);border:1px solid var(--borda-fina);border-radius:5px;
  padding:1px 6px}
.txt-compl{color:var(--txt2)}
.chip-inmet{display:inline-flex;align-items:center;gap:5px;
  border:1px solid;border-radius:999px;padding:2px 9px;font-size:.8rem;
  background:rgba(127,127,127,.08)}
.chip-inmet i{width:8px;height:8px;border-radius:50%;flex:0 0 auto}
.chip-inmet small{color:var(--txt2);font-size:.72rem}
.linha-arvore{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;padding:10px 12px;margin-bottom:10px}
.rotulo-linha{font-weight:800;letter-spacing:.4px}
.sub-arvore{color:var(--txt2);font-size:.78rem;margin-bottom:8px}
.nos{display:flex;flex-wrap:wrap;align-items:stretch;justify-content:center;gap:6px}
.no-arvore{flex:1 1 240px;max-width:360px;border:1px solid var(--borda-fina);
  border-radius:10px;padding:8px 10px;display:grid;
  grid-template-columns:auto 1fr;gap:4px 8px;align-items:start;
  text-align:left;font-size:.84rem}
.no-arvore{align-content:start}
/* fundo pastel + texto escuro: o par de maior contraste. O branco sobre
   laranja saturado tinha só ~2,3:1, abaixo de qualquer piso legível. */
.no-arvore.ativo{font-weight:600}
.no-arvore.ativo .motivo-no{border-top-color:rgba(0,0,0,.28);opacity:.92}
.no-arvore.inativo{opacity:.45}
.no-arvore .marca{font-weight:800}
.no-arvore .rotulo{grid-column:2}
.motivo-no{grid-column:2;font-size:.74rem;font-weight:400;line-height:1.35;
  opacity:.85;border-top:1px solid rgba(255,255,255,.22);padding-top:5px;
  margin-top:2px}
.no-arvore.inativo .motivo-no{border-top-color:var(--borda-fina)}
.conector{align-self:center;font-weight:800;color:var(--txt2);padding:0 2px}
/* 'OU' dentro do motivo de um bloco: é operador da regra, não palavra da
   frase — por isso recebe caixa alta, peso e um leve respiro em volta. */
.ou{font-weight:800;font-size:.92em;letter-spacing:.06em;opacity:.95;
    padding:0 2px;white-space:nowrap}
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

/* ── Previsão do tempo (Poaclima/Catavento) ──────────────────────────
   Cinco dias, cinco cartões. A chuva prevista ganha uma RÉGUA VERTICAL em
   vez de barra horizontal: a régua é o instrumento deste painel — o mesmo
   desenho que lê o rio lê a água que ainda vai cair — e a barra horizontal
   já está reservada para nível × cota. A escala da régua é comum aos cinco
   dias, então a altura da água se compara direto de um cartão ao outro. */
.fonte-prev{color:var(--txt2);font-size:.8rem;margin:2px 0 10px}
.previsao{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;
  margin-bottom:22px}
@media(max-width:1100px){.previsao{grid-template-columns:repeat(3,1fr)}}
@media(max-width:760px){.previsao{grid-template-columns:repeat(2,1fr)}}
@media(max-width:430px){.previsao{grid-template-columns:1fr}}
.dia-prev{background:var(--cartao);border:1px solid var(--borda);
  border-radius:12px;overflow:hidden;text-align:left;display:flex;
  flex-direction:column;box-shadow:0 2px 10px var(--sombra)}
.topo-prev{display:flex;align-items:baseline;justify-content:space-between;
  gap:6px;padding:7px 11px;border-bottom:1px solid var(--borda-fina);
  font-family:"Barlow Condensed",sans-serif}
.rot-dia{font-weight:700;font-size:1rem;letter-spacing:.12em;line-height:1}
.data-dia{color:var(--txt2);font-size:.82rem;letter-spacing:.04em;
  font-variant-numeric:tabular-nums}
/* O dia de hoje é a linha de base de qualquer decisão: recebe a única
   ênfase da faixa, no azul do CISC. */
.dia-prev.hoje{border-color:var(--cisc)}
.dia-prev.hoje .topo-prev{background:var(--cisc);border-bottom-color:transparent}
.dia-prev.hoje .rot-dia,.dia-prev.hoje .data-dia{color:#fff}
.corpo-prev{display:flex;align-items:center;gap:9px;padding:11px 11px 7px}
.ic-tempo{width:42px;height:42px;flex:0 0 auto}
.chuva-prev{flex:1 1 auto;min-width:0}
.mm-prev{font-family:"IBM Plex Mono",ui-monospace,monospace;font-weight:600;
  font-size:1.5rem;line-height:1.05;font-variant-numeric:tabular-nums}
.mm-prev small{font-size:.7rem;font-weight:500;opacity:.85;margin-left:2px}
.rot-chuva{color:var(--txt2);font-size:.7rem;text-transform:uppercase;
  letter-spacing:.06em;margin-top:2px;line-height:1.2}
.regua-chuva{position:relative;width:13px;height:54px;border-radius:7px;
  background:var(--trilho);border:1px solid var(--borda-fina);
  overflow:hidden;flex:0 0 auto}
.regua-chuva .agua{position:absolute;left:0;right:0;bottom:0;
  transition:height .4s ease}
.regua-chuva .marca{position:absolute;left:0;right:0;height:1px;
  background:var(--borda-fina)}
.desc-prev{padding:0 11px 9px;font-size:.85rem;line-height:1.28;
  min-height:2.4em;color:var(--txt)}
.metricas-prev{list-style:none;margin:0;padding:0 11px 11px;font-size:.82rem}
.metricas-prev li{display:flex;align-items:center;justify-content:space-between;
  gap:8px;padding:5px 0;border-top:1px solid var(--borda-fina)}
.metricas-prev .rot{color:var(--txt2);font-size:.68rem;text-transform:uppercase;
  letter-spacing:.07em}
.metricas-prev .val{font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.metricas-prev .val small{font-size:.68rem;font-weight:500;opacity:.85}
.t-max{color:#D9603B}
.t-min{color:#4FA3E3}
.barra-temp{color:var(--txt2);opacity:.6;padding:0 3px;font-weight:400}
.seta-vento{display:inline-block;color:var(--txt2);font-weight:700;
  margin:0 1px}
.sigla-vento{color:var(--txt2);font-size:.78rem;font-weight:700;
  letter-spacing:.04em}
.previsao-vazia{background:var(--cartao);border:1px dashed var(--borda);
  border-radius:12px;padding:12px 14px;margin-bottom:22px;
  color:var(--txt2);font-size:.9rem}
@media(prefers-reduced-motion:reduce){.regua-chuva .agua{transition:none}}

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

  /* Cabeçalho compacto na primeira página: identidade + velocímetro */
  .cabecalho{gap:10px;margin-bottom:4px;flex-wrap:nowrap;
             break-inside:avoid;page-break-inside:avoid}
  .identidade{flex:1 1 54%}
  .gauge-cabecalho{flex:0 0 42%;max-width:42%;min-width:0}
  .gauge-cabecalho .fig-claro,
  .gauge-cabecalho .fig-claro .js-plotly-plot,
  .gauge-cabecalho .fig-claro .plot-container,
  .gauge-cabecalho .fig-claro .svg-container{height:40mm !important}
  .logo{height:48px;width:40px}
  h1{font-size:1.68rem}
  .sub,.sobretitulo{font-size:.8rem}

  .trilho-estagios{margin-bottom:8px}
  .passo{font-size:.72rem;padding:6px 6px 6px 16px}
  .banner{padding:10px 14px;margin-bottom:10px;box-shadow:none}
  .banner h2{font-size:1.45rem}
  .banner .just{font-size:.82rem}

  /* Nada pode ser partido ao meio entre páginas */
  .banner,.card,.tile,.grafico,.bloco-regioes,.linha-regioes,.avisos-inmet,
  .avisos-dc,
  .linha-arvore,.cartao-chuva,.trilho-estagios,.no-arvore,.dia-prev,
  .previsao{break-inside:avoid;page-break-inside:avoid}

  /* Previsão: os cinco dias sempre em uma linha só na folha */
  .previsao{grid-template-columns:repeat(5,1fr) !important;gap:6px;
      margin-bottom:10px}
  .dia-prev{box-shadow:none}
  .topo-prev{padding:4px 7px}
  .rot-dia{font-size:.82rem}
  .data-dia{font-size:.7rem}
  .corpo-prev{padding:6px 7px 4px;gap:6px}
  .ic-tempo{width:30px;height:30px}
  .mm-prev{font-size:1.15rem}
  .regua-chuva{height:40px;width:11px}
  .desc-prev{padding:0 7px 5px;font-size:.72rem;min-height:0}
  .metricas-prev{padding:0 7px 6px;font-size:.7rem}
  .metricas-prev li{padding:3px 0}
  .metricas-prev .rot{font-size:.6rem}
  .fonte-prev{font-size:.66rem;margin-bottom:5px}

  .cards{display:grid !important;grid-template-columns:repeat(5,1fr);gap:7px}
  .card{max-width:none;flex:none !important;padding:7px;box-shadow:none}
  .card .est{min-height:0}
  .card .valor{font-size:1.3rem}

  .regioes-tela{display:none !important}
  .regioes-print{display:block !important}
  .linha-regioes{margin-bottom:5px}
  /* 6 por linha: 16,66% menos a folga dos 5 vãos de 8px */
  .linha-regioes .tile{flex:0 0 calc(16.66% - 8px);min-height:0;padding:5px 4px}

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
  document.querySelectorAll('.grafico .fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,
      'title.font.size':13,'legend.font.size':10,
      'margin.l':55,'margin.r':55,'margin.t':44,'margin.b':36});}catch(e){}
  });
  // o velocímetro do cabeçalho tem altura própria (40mm) e margens menores
  document.querySelectorAll('.gauge-cabecalho .fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,width:null,height:null,
      'margin.l':34,'margin.r':34,'margin.t':30,'margin.b':2});}catch(e){}
  });
}
function medidasDeTela(){
  document.querySelectorAll('.grafico .fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,width:null,height:340});}catch(e){}
  });
  document.querySelectorAll('.gauge-cabecalho .fig-claro .js-plotly-plot').forEach(function(g){
    try{Plotly.relayout(g,{autosize:true,width:null,height:215,
      'margin.l':42,'margin.r':42,'margin.t':38,'margin.b':4});}catch(e){}
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
  {_bloco_cabecalho(snapshot)}
  {_bloco_fontes(snapshot)}
  {_bloco_banner(snapshot)}
  {_bloco_cards(snapshot)}
  {_bloco_regioes(snapshot)}
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
