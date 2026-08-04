# -*- coding: utf-8 -*-
"""
acoes_estagio.py
================
Ações recomendadas para cada ESTÁGIO OPERACIONAL, em duas faixas de leitura:

* SERVIDORES DA SAÚDE  — o que a rede SMS faz neste estágio
* POPULAÇÃO EM GERAL   — o que o morador de Porto Alegre faz neste estágio

Fonte: Plano de Contingência para Emergências em Saúde Pública por Chuvas
Intensas e Desastres Associados — SMS/PMPA, 2ª edição (item 5.1.1, Quadros
5 a 9). O Plano lista as ações por SETOR e SUBSETOR, em texto longo; aqui
elas viram tópicos curtos, porque o painel é lido em pé, no meio do evento,
muitas vezes no celular. Quem precisa do detalhe vai ao documento — o
painel diz o que fazer AGORA.

A coluna da população não está no Plano com essas palavras: ela condensa as
orientações de comunicação de risco à população previstas no próprio Plano
(água segura, leptospirose, evacuação preventiva, abrigos, canais oficiais).

Para editar o conteúdo, mexa só no dicionário ACOES abaixo.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────
# CONTEÚDO — é aqui que se edita
# ──────────────────────────────────────────────────────────────────────────
ACOES: dict[str, dict[str, list[str]]] = {

    "NORMALIDADE": {
        "servidores": [
            "Acompanhar diariamente avisos e alertas meteorológicos e hidrológicos",
            "Manter o POP da equipe atualizado, com responsáveis e contatos",
            "Conferir estoques de medicamentos, insumos, EPIs e imunobiológicos",
            "Revisar plano de evacuação, gerador e comunicação sem internet ou energia",
            "Manter atualizada a lista de profissionais voluntários",
            "Seguir com a vigilância de rotina: arboviroses, zoonoses e doenças de veiculação hídrica",
        ],
        "populacao": [
            "Acompanhar as informações oficiais da Defesa Civil e da Prefeitura",
            "Manter a vacinação em dia, inclusive a do tétano",
            "Limpar calhas e ralos; não jogar lixo em bocas de lobo e arroios",
            "Eliminar criadouros do mosquito da dengue",
            "Saber se a sua casa fica em área com histórico de alagamento",
            "Ter um kit pronto: documentos em saco plástico, água, remédios de uso contínuo, lanterna e carregador",
        ],
    },

    "MOBILIZAÇÃO": {
        "servidores": [
            "Repassar os avisos e alertas a toda a equipe pelo fluxo já definido",
            "Verificar quais unidades e serviços ficam em área sujeita a alagamento",
            "Avaliar remanejo preventivo de estoques, medicamentos e imunobiológicos",
            "Identificar pacientes de alta complexidade na área de risco (diálise, oxigênio, oncológicos, gestantes, acamados)",
            "Avaliar cancelamento de consultas e exames eletivos",
            "Reforçar contato com Defesa Civil, Assistência Social e 1ª CRS",
            "Testar comunicação alternativa e conferir geradores",
        ],
        "populacao": [
            "Acompanhar a previsão e os alertas oficiais; desconfiar de mensagens em corrente",
            "Evitar áreas com histórico de alagamento e não atravessar pontos alagados",
            "Em área de risco, tirar do chão documentos, remédios e eletrodomésticos",
            "Separar remédios de uso contínuo e receitas para levar se precisar sair",
            "Carregar celular e baterias",
            "Combinar com a família para onde ir caso seja preciso deixar a casa",
        ],
    },

    "ALERTA": {
        "servidores": [
            "Acionar os protocolos de alerta e preparação da equipe",
            "Remanejar estoques, equipes e pacientes das unidades em risco",
            "Suspender ou reagendar eletivos e comunicar os usuários",
            "Apoiar Assistência Social e Defesa Civil nos abrigos abertos: condições sanitárias, vacinação e atendimento",
            "Acionar equipes volantes e Primeiros Socorros Psicológicos",
            "Definir rotas alternativas para insumos, equipes e pacientes",
            "Reforçar notificação de leptospirose, diarreias e acidentes ligados ao evento",
        ],
        "populacao": [
            "Em área de risco, saia antes de a água chegar — não espere",
            "Não entre em contato com a água da enchente; se entrar, lave-se com água limpa e sabão",
            "Febre, dor de cabeça ou dor muscular depois do contato com a água: procure a unidade de saúde",
            "Ao ir para abrigo, leve documentos, remédios e receitas",
            "Beba só água tratada, fervida ou clorada",
            "Defesa Civil 199 · Bombeiros 193 · SAMU 192 · Prefeitura 156",
        ],
    },

    "SITUAÇÃO DE EMERGÊNCIA": {
        "servidores": [
            "Compor e seguir o Centro de Operações de Emergência (COE)",
            "Informar diariamente quais serviços seguem abertos e quais foram interrompidos",
            "Priorizar urgências e a continuidade do cuidado de crônicos e alta complexidade",
            "Atuar nos abrigos: vigilância sindrômica, vacinação, saúde mental, vetores e zoonoses",
            "Garantir água segura e distribuir hipoclorito onde o abastecimento parou",
            "Registrar atendimentos mesmo offline, em formulário de papel",
            "Cuidar da equipe: escala, EPI, vacinação e apoio em saúde mental",
        ],
        "populacao": [
            "Siga a orientação de evacuação e não volte para casa antes da liberação",
            "Não consuma alimento ou remédio que teve contato com a água da enchente",
            "Use apenas água potável distribuída, fervida ou tratada com hipoclorito",
            "Na limpeza, use botas e luvas e desinfete com água sanitária",
            "Febre, diarreia ou dor no corpo após a enchente: procure atendimento e avise do contato com a água",
            "Atenção a fios elétricos e a animais peçonhentos trazidos pela água",
            "Informe-se apenas por canais oficiais: 199, 193, 192 e 156",
        ],
    },

    "CRISE": {
        "servidores": [
            "COE ativado: toda decisão e toda informação passam por ele",
            "Operar em modo offline: registro em papel, rádio ou telefone, backup dos dados",
            "Manter apenas os serviços essenciais, postos avançados e hospitais de campanha",
            "Solicitar apoio estadual e federal; organizar voluntários, doações e ajuda humanitária",
            "Vacinar equipes, socorristas e abrigados (tétano, hepatite A, influenza, COVID)",
            "Vigilância intensificada de surtos, óbitos, água, alimentos e vetores nas áreas isoladas",
            "Rodízio das equipes e apoio psicológico ao trabalhador da saúde",
        ],
        "populacao": [
            "Priorize a vida: aceite a evacuação e leve apenas o essencial",
            "Não entre em áreas isoladas, alagadas ou com risco de deslizamento",
            "Se estiver ilhado, sinalize o local e informe quantas pessoas, idosos, crianças e doentes crônicos há ali",
            "Consuma só água de fonte oficial ou tratada",
            "Continue o tratamento de doenças crônicas: procure a equipe de saúde do abrigo para receita e medicamento",
            "Medo, insônia e tristeza são reações esperadas — há atendimento em saúde mental",
            "Confie apenas nos canais oficiais: 199, 193, 192 e 156",
        ],
    },
}

# Quando falta dado para classificar, o painel mostra DADOS INSUFICIENTES.
# Não existe coluna do Plano para isso — a conduta é a de precaução: seguir
# as ações do estágio de MOBILIZAÇÃO até a coleta normalizar.
ESTAGIO_PADRAO = "MOBILIZAÇÃO"

FAIXAS = [
    ("servidores", "Servidores da saúde", "Rede SMS · equipes e serviços"),
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
        <div class="faixa-acoes" style="border-color:{borda}">
          <div class="cabeca-acoes" style="background:{borda};color:{tinta}">
            <span class="tit">{titulo}</span>
            <span class="sub">{sub}</span>
          </div>
          <ul class="lista-acoes" style="background:{fundo}">{itens}</ul>
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
       margin-bottom:22px;text-align:left}
.faixa-acoes{flex:1 1 calc(50% - 12px);min-width:280px;border:2px solid;
       border-radius:12px;overflow:hidden;background:var(--cartao);
       box-shadow:0 2px 10px var(--sombra)}
.cabeca-acoes{padding:9px 14px 8px}
.cabeca-acoes .tit{display:block;font-family:"Barlow Condensed",sans-serif;
       font-weight:700;font-size:1.22rem;letter-spacing:.04em;
       text-transform:uppercase;line-height:1.1}
.cabeca-acoes .sub{display:block;font-size:.76rem;opacity:.88}
.lista-acoes{margin:0;padding:12px 16px 14px 32px;color:#12202E;
       font-size:.93rem;line-height:1.45}
.lista-acoes li{margin:0 0 6px}
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
  .cabeca-acoes .sub{font-size:.62rem}
  .lista-acoes{font-size:.68rem;line-height:1.3;padding:6px 10px 7px 22px}
  .lista-acoes li{margin:0 0 3px}
  .aviso-acoes{font-size:.66rem;padding:4px 9px;margin-bottom:5px}
}
"""
