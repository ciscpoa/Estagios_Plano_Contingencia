# -*- coding: utf-8 -*-
"""
acoes_estagio.py
================
Ações recomendadas para cada ESTÁGIO OPERACIONAL, em duas faixas de leitura:

* TRABALHADORES DA SAÚDE — o que a rede SMS faz neste estágio
* POPULAÇÃO EM GERAL     — o que o morador de Porto Alegre faz neste estágio

Conteúdo: "Ações Recomendadas por Estágio Operacional" — SMS/Porto Alegre,
resumo operacional do Plano de Contingência da SMS (item 5.1.1). Os textos
deste módulo seguem esse documento; a apresentação em cartões permanece a
mesma do painel.

Para editar o conteúdo, mexa só no dicionário ACOES abaixo.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────
# CONTEÚDO — é aqui que se edita
# ──────────────────────────────────────────────────────────────────────────
ACOES: dict[str, dict[str, list[str]]] = {

    "NORMALIDADE": {
        "servidores": [
            "Acompanhar diariamente avisos e alertas meteorológicos e hidrológicos emitidos pelas autoridades competentes",
            "Identificar unidades e serviços em área sujeita a alagamento, inundação ou deslizamento",
            "Manter Planos e Procedimentos Operacionais Padrão de preparação e resposta das equipe atualizados. Incluir responsáveis, contatos e rotas alternativas de fuga e deslocamento.",
            "Montar kit de emergência para necessidade e evacuação (EPIs, equipamentos eletrônicos, formulários impressos, materiais de escritório)",
            "Identificar grupos vulneráveis e pacientes de alta complexidade nas áreas de risco (diálise, oxigênio, oncológicos, gestantes, acamados, domiciliados)",
            "Manter ciclo de capacitação e educação permanente em Emergências em Saúde Pública",
            "Manter atualizada a lista de profissionais voluntários",
        ],
        "populacao": [
            "Acompanhar as informações oficiais da Defesa Civil e da Prefeitura Municipal",
            "Manter a vacinação em dia, inclusive a do tétano",
            "Conhecer os pontos com histórico de alagamento, inundação ou com risco de deslizamento do seu bairro",
            "Conhecer as organizações comunitárias e os espaços seguros para se abrigar do seu bairro",
            "Ter um kit de emergência pronto: documentos pessoais em saco plástico, água potável, remédios de uso contínuo, roupa íntima, lanterna e carregador",
            "Limpar calhas e ralos",
            "Não jogar lixo em bocas de lobo e arroios",
            "Eliminar criadouros do mosquito da dengue",
        ],
    },

    "MOBILIZAÇÃO": {
        "servidores": [
            "Repassar os avisos e alertas a toda a equipe pelo fluxo definido",
            "Acompanhar a evolução dos Estágios Operacionais do Plano de Contingência",
            "Rever quais as unidades e serviços ficam em área sujeita a alagamento, inundação ou deslizamento",
            "Avaliar necessidade de remanejo preventivo de estoques, medicamentos e imunobiológicos nas áreas de maior risco",
            "Avaliar necessidade de cancelamento de consultas e exames eletivos nas áreas de maior risco",
            "Reforçar contato com Defesa Civil, Assistência Social e a 1ª Coordenadoria Regional de Saúde",
            "Revisar kit de emergência (EPIs, equipamentos eletrônicos, formulários impressos, materiais de escritório)",
            "Conferir funcionamento dos geradores elétricos",
            "Testar equipamentos e sistemas alternativos de comunicação que funcionem sem depender de redes de telefonia ou internet, como rádios comunicadores, sistemas de alto-falantes e aplicativos offline.",
        ],
        "populacao": [
            "Acompanhar a previsão e os alertas oficiais",
            "Desconfiar de mensagens com títulos sensacionalistas",
            "Evitar deslocamentos desnecessários e manter-se em local abrigado",
            "Em área de risco de alagamento ou inundação, elevar eletrodomésticos e proteger documentos e remédios",
            "Carregar celular e baterias",
            "Separar o kit de emergência pronto para levar se precisar sair: documentos pessoais em saco plástico, água potável, receitas e remédios de uso contínuo, roupa íntima, lanterna e carregador",
            "Combinar com a família para onde ir caso seja preciso deixar sua casa",
        ],
    },

    "ALERTA": {
        "servidores": [
            "Acionar os protocolos de alerta e preparação da equipe",
            "Remanejar estoques, equipes e pacientes das unidades de saúde de maior risco",
            "Suspender ou reagendar consultas eletivas e comunicar os usuários",
            "Apoiar Assistência Social e Defesa Civil nos abrigos abertos: condições sanitárias, vacinação e atendimento",
            "Acionar equipes volantes e Primeiros Socorros Psicológicos",
            "Acionar rotas alternativas para insumos, equipes e pacientes",
            "Reforçar notificação de leptospirose, diarréias, violências e acidentes ligados ao evento",
        ],
        "populacao": [
            "Em área de risco, saia antes da água chegar — não espere",
            "Acompanhar a previsão e os alertas oficiais;",
            "Desconfiar de mensagens em corrente e com títulos sensacionalistas",
            "Evitar deslocamentos desnecessários e manter-se em local abrigado",
            "Pegar o kit de emergência pronto: documentos pessoais em saco plástico, água potável, remédios de uso contínuo, roupa íntima, lanterna e carregador",
            "Se precisar sair de casa, comunique a família e informe para onde vai",
            "Use botas de borracha e luvas impermeáveis para mexer com lama ou entulhos",
            "Se tiver contato com a água da enchente, lave-se com água limpa e sabão",
            "Se tiver febre, dor de cabeça ou dor muscular depois do contato com a água: procure a unidade de saúde",
            "Ao ir para abrigo, leve documentos, remédios e receitas",
            "Beba só água tratada, fervida ou clorada",
            "Defesa Civil 199 · Bombeiros 193 · SAMU 192 · Prefeitura 156",
        ],
    },

    "SITUAÇÃO DE EMERGÊNCIA": {
        "servidores": [
            "Compor ou acompanhar os comandos do Centro de Operações de Emergência (COE)",
            "Informar diariamente quais serviços quais estão abertos e quais tiveram funcionamento suspenso",
            "Priorizar urgências e a continuidade do cuidado de crônicos e alta complexidade",
            "Atuar nos abrigos: prestar assistência às condições agudas, às pessoas com condições crônicas que possam descompensar, realizar ações de vacinação e de saúde mental, e identificar doenças transmissíveis relacionadas ao evento",
            "Disponibilizar água potável e distribuir hipoclorito onde teve interrupção de abastecimento",
            "Registrar atendimentos mesmo offline, em formulário de papel",
            "Cuidar da equipe: escala, EPI, vacinação e apoio em saúde mental",
        ],
        "populacao": [
            "Priorize a sua vida: Se você receber orientação para sair de casa, aceite. Leve apenas o kit de emergência pronto - documentos pessoais em saco plástico, água potável, remédios de uso contínuo, roupa íntima, lanterna e carregador",
            "Se precisar sair de casa, comunique a família e informe para onde vai",
            "Não consuma alimento ou remédio que teve contato com a água da enchente",
            "Use apenas água potável distribuída, fervida ou tratada com hipoclorito",
            "Na limpeza, use botas e luvas impermeáveis e desinfete pisos, paredes e utensílios com água sanitária",
            "Se tiver febre, diarréia ou dor no corpo: procure atendimento",
            "Se precisar de atendimento de saúde, informe se teve contato com a água de enchente, se comeu alimento que teve contato com a água da enchente, acidente com animal peçonhento ou mordidas, ou se está em abrigo temporário",
            "Atenção a fios elétricos caídos na água. Mantenha distância para evitar choques elétricos.",
            "Desconfiar de mensagens em corrente e com títulos sensacionalistas",
            "Acione contatos de emergência: 199 (Defesa Civil), 193 (Bombeiros), 192 (SAMU) e 156 (Central de Atendimento ao Cidadão de Porto Alegre)",
        ],
    },

    "CRISE": {
        "servidores": [
            "Centro de Operações de Emergência (COE) ativado: toda decisão e toda informação passam por este centro",
            "Operar em modo offline: registro em papel, rádio ou telefone, backup dos dados",
            "Manter apenas os serviços essenciais, postos avançados e hospitais de campanha",
            "Organizar voluntários, doações e ajuda humanitária",
            "Vacinar equipes, socorristas e abrigados (tétano, hepatite A, influenza, Covid-19)",
            "Vigilância intensificada de surtos, óbitos, água, alimentos e vetores nas áreas atingidas, isoladas e abrigos",
            "Rodízio das equipes e apoio psicológico ao trabalhador da saúde",
        ],
        "populacao": [
            "Priorize a sua vida: Se você receber orientação para sair de casa, aceite. Leve apenas o kit de emergência pronto - documentos pessoais em saco plástico, água potável, remédios de uso contínuo, roupa íntima, lanterna e carregador",
            "Não entre em áreas isoladas, alagadas ou com risco de deslizamento",
            "Não consuma alimento ou remédio que teve contato com a água da enchente",
            "Use apenas água potável distribuída, fervida ou tratada com hipoclorito",
            "Se tiver febre, diarreia ou dor no corpo: procure atendimento",
            "Se precisar de atendimento de saúde, informe se teve contato com a água de enchente, se comeu alimento que teve contato com a água da enchente, acidente com animal peçonhento ou mordidas, ou se está em abrigo temporário",
            "Atenção a fios elétricos caídos na água. Mantenha distância para evitar choques elétricos.",
            "Se estiver em um abrigo temporário continue o tratamento de doenças crônicas: procure a equipe de saúde do abrigo para receita e medicamento",
            "Medo, insônia e tristeza são reações esperadas — busque atendimento em saúde mental",
            "Desconfiar de mensagens em corrente e com títulos sensacionalistas",
            "Acione contatos de emergência: 199 (Defesa Civil), 193 (Bombeiros), 192 (SAMU) e 156 (Central de Atendimento ao Cidadão de Porto Alegre)",
        ],
    },
}

# Quando falta dado para classificar, o painel mostra DADOS INSUFICIENTES.
# Não existe coluna do Plano para isso — a conduta é a de precaução: seguir
# as ações do estágio de MOBILIZAÇÃO até a coleta normalizar.
ESTAGIO_PADRAO = "MOBILIZAÇÃO"

FAIXAS = [
    ("servidores", "Trabalhadores da saúde", "Rede SMS · equipes e serviços"),
    ("populacao", "População em geral", "Moradores de Porto Alegre"),
]


# ──────────────────────────────────────────────────────────────────────────
# HTML
# ──────────────────────────────────────────────────────────────────────────
def _escapa(txt: str) -> str:
    return (str(txt).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _pastel(hexa: str, mistura: float = 0.82) -> str:
    """Mesma ideia do resto do painel: matiz do Plano, saturação baixa —
    fundo pastel aceita texto preto, que é o que se lê de longe."""
    h = (hexa or "#888888").lstrip("#")
    if len(h) != 6:
        return "#FFFFFF"
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#FFFFFF"
    m = max(0.0, min(1.0, mistura))
    return "#%02X%02X%02X" % tuple(round(c + (255 - c) * m) for c in (r, g, b))


def _tinta(hexa: str) -> str:
    """Branco ou quase-preto sobre a cor cheia, pelo contraste real: branco
    sobre o amarelo da MOBILIZAÇÃO não se lê."""
    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    h = (hexa or "#000000").lstrip("#")
    if len(h) != 6:
        return "#FFFFFF"
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#FFFFFF"
    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    razao_branco = 1.05 / (lum + 0.05)
    lum_escura = 0.2126 * lin(0x12) + 0.7152 * lin(0x20) + 0.0722 * lin(0x2E)
    razao_escura = ((max(lum, lum_escura) + 0.05)
                    / (min(lum, lum_escura) + 0.05))
    return "#FFFFFF" if razao_branco >= razao_escura else "#12202E"


def bloco(snapshot: dict) -> str:
    """Seção 'Ações recomendadas' — entra logo abaixo do banner do estágio."""
    cls = snapshot.get("classificacao") or {}
    estagio = (cls.get("estagio") or "").strip().upper()
    cor = cls.get("cor") or "#2E9E44"

    conteudo = ACOES.get(estagio)
    aviso = ""
    if conteudo is None:
        conteudo = ACOES[ESTAGIO_PADRAO]
        cor = "#4A5561"
        aviso = ("<div class='aviso-acoes'>Sem classificação automática no "
                 "momento: por precaução, valem as ações de "
                 f"{ESTAGIO_PADRAO}.</div>")

    rotulo = cls.get("rotulo") or estagio or "—"
    fundo, borda, tinta = _pastel(cor), cor, _tinta(cor)

    colunas = []
    for chave, titulo, sub in FAIXAS:
        itens = "".join(f"<li>{_escapa(i)}</li>"
                        for i in conteudo.get(chave, []))
        colunas.append(f"""
        <div class="faixa-acoes" style="border-color:{borda};background:{fundo}">
          <div class="cabeca-acoes" style="background:{borda};color:{tinta}">
            <span class="tit">{titulo}</span>
            <span class="sub">{sub}</span>
          </div>
          <ul class="lista-acoes">{itens}</ul>
        </div>""")

    return f"""
    <h3 class="titulo-secao">Ações recomendadas — {_escapa(rotulo)}</h3>
    <div class="sub-secao">Resumo operacional do Plano de Contingência da
      SMS (item 5.1.1). Não substitui o documento completo nem as
      orientações da Defesa Civil.</div>
    {aviso}
    <section class="acoes">{''.join(colunas)}</section>"""


# ──────────────────────────────────────────────────────────────────────────
# CSS — injetado pelo site_estatico.py em <style>
# ──────────────────────────────────────────────────────────────────────────
CSS = """
.acoes{display:flex;flex-wrap:wrap;gap:12px;justify-content:center;
       margin-bottom:22px;text-align:left;align-items:stretch}
/* O fundo pastel é do CARTÃO, não da lista: as duas colunas esticam juntas
   (align-items:stretch), então a coluna com menos tópicos terminava com uma
   faixa do fundo escuro sobrando embaixo da lista. */
.faixa-acoes{flex:1 1 calc(50% - 12px);min-width:280px;border:2px solid;
       border-radius:12px;overflow:hidden;box-shadow:0 2px 10px var(--sombra);
       display:flex;flex-direction:column}
.cabeca-acoes{padding:9px 14px 8px}
.cabeca-acoes .tit{display:block;font-family:"Barlow Condensed",sans-serif;
       font-weight:700;font-size:1.22rem;letter-spacing:.04em;
       text-transform:uppercase;line-height:1.1}
/* color:inherit obrigatório: existe um `.sub{color:var(--txt2)}` global no
   cabeçalho da página que vencia a herança e pintava este subtítulo de
   cinza-claro sobre o amarelo — ilegível. Aqui ele volta à tinta escura
   calculada para a cor do estágio. */
.cabeca-acoes .sub{display:block;font-size:.78rem;font-weight:600;
       color:inherit;opacity:1}
.lista-acoes{flex:1 1 auto;margin:0;padding:12px 16px 14px 32px;
       background:transparent;color:#12202E;font-size:.93rem;line-height:1.45}
.lista-acoes li{margin:0 0 6px}
.lista-acoes li::marker{color:#12202E}
.lista-acoes li:last-child{margin-bottom:0}
.aviso-acoes{background:#8a6d1a;color:#fff;border-radius:10px;
       padding:8px 14px;margin-bottom:10px;font-size:.86rem}
@media(max-width:760px){.faixa-acoes{flex:1 1 100%}
  .lista-acoes{font-size:.9rem;padding-left:28px}}

@media print{
  .acoes{display:grid !important;grid-template-columns:1fr 1fr;gap:7px;
         margin-bottom:8px}
  .faixa-acoes{border-width:1pt;box-shadow:none;
         break-inside:avoid;page-break-inside:avoid}
  .cabeca-acoes{padding:4px 9px 3px}
  .cabeca-acoes .tit{font-size:.95rem}
  .cabeca-acoes .sub{font-size:.64rem}
  .lista-acoes{font-size:.68rem;line-height:1.3;padding:6px 10px 7px 22px}
  .lista-acoes li{margin:0 0 3px}
  .aviso-acoes{font-size:.66rem;padding:4px 9px;margin-bottom:5px}
}
"""
