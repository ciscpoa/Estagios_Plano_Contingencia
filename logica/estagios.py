# -*- coding: utf-8 -*-
"""
estagios.py
===========
TAREFA 3 — Classificação de Porto Alegre em um dos 5 ESTÁGIOS OPERACIONAIS
do Plano de Contingência (item 5.1), com regras E / OU transcritas da
imagem oficial da SMS/PMPA:

  1. NORMALIDADE (verde)
  2. MOBILIZAÇÃO (amarelo)
  3. ALERTA (laranja)
  4. SITUAÇÃO DE EMERGÊNCIA (vermelho)
  5. CRISE (roxo)

Estratégia (conforme nota do projeto):
  * Os gatilhos MATEMÁTICOS (cotas ANA + precipitação Open-Meteo/INMET)
    são a base primária da classificação automática.
  * Os gatilhos QUALITATIVOS (interrupção de energia, óbitos, abrigos...)
    entram como variáveis BOOLEANAS no dataclass `InputsInfraestrutura`,
    preenchíveis manualmente ou por integrações futuras.
  * Blocos "E" qualitativos sem input manual são tratados por PROXY:
    quando os sinais numéricos são fortes o suficiente, o bloco conta
    como satisfeito (comportamento configurável em `modo_estrito`).

A avaliação é feita de cima para baixo (CRISE → NORMALIDADE) e retorna o
estágio mais grave cujos gatilhos foram atendidos, junto com a lista de
justificativas (auditoria de cada regra disparada).
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

import config


# ──────────────────────────────────────────────────────────────────────────
# INPUTS
# ──────────────────────────────────────────────────────────────────────────
@dataclass
class InputsInfraestrutura:
    """Gatilhos qualitativos (preenchidos manualmente ou por integrações)."""
    # ALERTA
    familias_deixando_casas: bool = False
    aumento_demanda_abrigo: bool = False
    abrigos_temporarios_instalados: bool = False
    bloqueio_vias_principais: bool = False
    aumento_demanda_saude_clima: bool = False
    # EMERGÊNCIA
    inundacoes_graves_ou_deslizamentos: bool = False
    vias_ou_pontes_danificadas: bool = False
    interrupcao_parcial_servicos_essenciais: bool = False
    aumento_significativo_desabrigados: bool = False
    obitos_pelo_evento: bool = False
    servicos_saude_interrompidos: bool = False
    risco_alto_desabastecimento: bool = False
    # CRISE
    colapso_drenagem_urbana: bool = False
    interrupcao_infraestrutura_grande_escala: bool = False
    isolamento_areas_comunidades: bool = False
    descontrole_rede_abrigos: bool = False
    sobrecarga_sistema_saude: bool = False
    necessidade_apoio_federal_estadual: bool = False


@dataclass
class IndicadoresNumericos:
    """Sinais matemáticos extraídos das APIs (ANA + Open-Meteo + INMET)."""
    nivel_guaiba_m: float | None = None
    tendencia_guaiba_48h_m: float | None = None       # Δ nível em 48h
    dias_guaiba_acima_inundacao: int = 0              # persistência acima da cota

    # afluentes: {nome: {"nivel_m":..., "tendencia_48h_m":...}}
    afluentes: dict = field(default_factory=dict)

    acumulado_obs_24h_mm: float = 0.0
    acumulado_obs_72h_mm: float = 0.0
    acumulado_obs_96h_mm: float = 0.0     # janela de CONVENÇÃO exibida no painel
    acumulado_obs_5d_mm: float = 0.0      # 5 dias: card, simétrico à previsão
    acumulado_obs_7d_mm: float = 0.0
    previsto_48h_mm: float = 0.0
    dias_chuva_intensa_5d: int = 0

    # ── Previsão estendida: "as previsões indicam CONTINUIDADE do padrão" ──
    # O Plano fala em continuidade, não só em volume nas próximas 48h. Uma
    # semana com 15+15+25+40 mm/dia é continuidade, mesmo sem pico em 48h.
    previsto_72h_mm: float = 0.0
    previsto_5d_mm: float = 0.0
    dias_previsao_chuva: int = 0          # dias com chuva relevante previstos
    dias_com_chuva_obs_5d: int = 0        # dias com chuva relevante já ocorridos

    # Procedência da chuva observada (auditoria no painel)
    fonte_chuva_obs: str | None = None      # nome CURTO (ex.: "ANA · Gravataí")
    fonte_chuva_prev: str | None = None
    qualidade_chuva_obs: str | None = None

    inmet_max_severidade: str | None = None           # Amarelo/Laranja/Vermelho
    poaclima_alerta: str | None = None
    metropole_em_alerta: bool = False                 # cidade da RM já em alerta

    # Medidores do Poaclima (Selenium): 2ª leitura do Guaíba + córrego urbano
    poaclima_gasometro_m: float | None = None
    poaclima_cais_maua_m: float | None = None
    poaclima_riacho_ipiranga_m: float | None = None

    # Alertas regionais do Poaclima (popups por subprefeitura/região):
    # [{"regiao_num", "regiao_nome", "risco", "tipo", "inicio", "fim", ...}]
    alertas_regionais: list = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────
def _lista(itens) -> str:
    """
    Enumeração com marcador, um item por linha.

    Aqui NÃO entra ' OU '. Estes itens são as MEDIÇÕES que sustentam o
    gatilho (quais afluentes estão em cota, quais gatilhos foram
    confirmados) — todas verdadeiras ao mesmo tempo. O ' OU ' do Plano
    opera um nível acima, entre as condições alternativas, e por isso vive
    no TÍTULO do bloco, não na lista de evidências.
    """
    return "\n".join(f"• {str(i).strip()}" for i in itens if str(i).strip())


def _nome(chave: str) -> str:
    """Nome de exibição da estação (sem underlines)."""
    return config.NOMES_EXIBICAO.get(chave, chave.replace("_", " "))


def _nivel_de(dados: dict) -> float | None:
    """Nível de um resumo de estação (aceita 'nivel_m' ou 'nivel_atual_m')."""
    v = dados.get("nivel_m")
    return v if v is not None else dados.get("nivel_atual_m")


# As três cotas do SAH, da menos grave para a mais grave. A ordem é o que
# permite dizer que quem passou da INUNDAÇÃO obviamente passou da atenção.
ORDEM_COTAS = ("atencao", "alerta", "inundacao")
ROTULO_COTA = {"atencao": "atenção", "alerta": "alerta",
               "inundacao": "inundação"}


def _cota_atingida(refs: dict, nivel: float | None) -> tuple[str, float] | None:
    """
    A cota MAIS GRAVE que aquela régua já ultrapassou — ou None.

    SÓ cotas oficiais entram aqui. Estimar a cota de atenção/alerta por
    fração da de inundação foi tentado e desfeito: número inventado num
    painel de proteção civil vira, na leitura de quem decide, número
    oficial. Régua com apenas a cota de inundação publicada (Jacuí em
    Cachoeira do Sul) só dispara ao cruzar essa cota; enquanto isso o
    percentual no card segue mostrando a proximidade.

    A varredura vai da menos grave para a mais grave e fica com a última:
    um rio acima da cota de alerta está, por definição, acima da de
    atenção, e a ausência da cota intermediária não pode apagá-lo da lista
    (foi o caso do Gravataí, que não tem cota de atenção publicada).
    """
    if nivel is None:
        return None
    achada = None
    for chave in ORDEM_COTAS:
        ref = (refs or {}).get(chave)
        if ref is not None and nivel >= ref:
            achada = (chave, ref)      # fica com a última (mais grave)
    return achada


def _refs_afluente(nome: str) -> dict:
    return config.COTAS_AFLUENTES.get(nome) or {}


def _refs_guaiba() -> dict:
    return {"atencao": config.COTA_ATENCAO_GUAIBA,
            "alerta": config.COTA_ALERTA_GUAIBA,
            "inundacao": config.COTA_INUNDACAO_GUAIBA}


def _refs_riacho() -> dict:
    return {"atencao": getattr(config, "COTA_ATENCAO_RIACHO_IPIRANGA", None),
            "alerta": getattr(config, "COTA_ALERTA_RIACHO_IPIRANGA", None),
            "inundacao": getattr(config, "COTA_INUNDACAO_RIACHO_IPIRANGA", None)}


def _frase_cota(rotulo: str, nivel: float, atingida: tuple[str, float]) -> str:
    """'Gravataí 4,68 m (≥ alerta 4,25 m)' — sempre dizendo QUAL cota é."""
    chave, ref = atingida
    return f"{rotulo} {nivel:.2f} m (≥ {ROTULO_COTA[chave]} {ref:.2f} m)"


def _rios_em_cota(ind: IndicadoresNumericos, nivel_guaiba: float | None,
                  minima: str = "atencao") -> list[str]:
    """
    Todas as réguas que já passaram pelo menos a cota `minima`, cada uma com
    a cota que efetivamente atingiu. Lista completa, sem corte: quem lê o
    painel precisa saber quantos rios estão na faixa, não uma amostra.
    """
    piso = ORDEM_COTAS.index(minima)
    frases = []
    pares = [("Guaíba", _refs_guaiba(), nivel_guaiba),
             ("Ipiranga", _refs_riacho(), ind.poaclima_riacho_ipiranga_m)]
    pares += [(_nome(nome), _refs_afluente(nome), _nivel_de(dados))
              for nome, dados in ind.afluentes.items()]
    for rotulo, refs, nivel in pares:
        atingida = _cota_atingida(refs, nivel)
        if atingida and ORDEM_COTAS.index(atingida[0]) >= piso:
            frases.append(_frase_cota(rotulo, nivel, atingida))
    return frases


def _afluente_atingiu(ind: IndicadoresNumericos, cota: str) -> bool:
    """True se algum afluente atingiu PELO MENOS a cota pedida."""
    piso = ORDEM_COTAS.index(cota)
    for nome, dados in ind.afluentes.items():
        atingida = _cota_atingida(_refs_afluente(nome), _nivel_de(dados))
        if atingida and ORDEM_COTAS.index(atingida[0]) >= piso:
            return True
    return False


def _afluente_subindo(ind: IndicadoresNumericos) -> bool:
    """True se algum afluente apresenta tendência de subida relevante."""
    for dados in ind.afluentes.values():
        t = dados.get("tendencia_48h_m")
        if t is not None and t >= config.TENDENCIA_SUBIDA_RELEVANTE_M:
            return True
    return False


def _nivel_guaiba_efetivo(ind: IndicadoresNumericos) -> float | None:
    """
    Nível "efetivo" do Guaíba: o MAIOR entre a leitura da ANA e os dois
    medidores do Guaíba no Poaclima (Usina do Gasômetro e Cais Mauá).

    Usar o máximo é a postura conservadora correta para proteção civil:
    se qualquer medidor confiável indica cota atingida, o gatilho vale.
    """
    leituras = [v for v in (ind.nivel_guaiba_m,
                            ind.poaclima_gasometro_m,
                            ind.poaclima_cais_maua_m) if v is not None]
    return max(leituras) if leituras else None


def _corregos_subindo(ind: IndicadoresNumericos) -> tuple[bool, str | None]:
    """
    Gatilho "os córregos da cidade começam a subir significativamente"
    (bloco 2 do ALERTA), medido pelo Riacho Ipiranga/Arroio Dilúvio no
    Poaclima. Retorna (disparou, motivo).
    """
    nivel = ind.poaclima_riacho_ipiranga_m
    cota = config.COTA_ALERTA_RIACHO_IPIRANGA
    if nivel is None or cota is None:
        return False, None
    if nivel >= cota:
        return True, (f"Riacho Ipiranga em {nivel:.2f} m "
                      f"(≥ cota de alerta {cota:.2f} m) — córregos da cidade subindo")
    return False, None


def _resumo_alertas_regionais(ind: IndicadoresNumericos) -> dict:
    """
    Resume os alertas regionais do Poaclima (Defesa Civil por subprefeitura):
      n_total ......................... qualquer alerta vigente
      n_inundacao_risco_elevado ....... regiões com Inundação em risco alto+
      regioes_inundacao ............... nomes dessas regiões (p/ justificativa)
    """
    n_total = 0
    regioes_inundacao: list[str] = []
    regioes_todas: list[str] = []
    for al in ind.alertas_regionais or []:
        risco = (al.get("risco") or "").lower()
        tipo = (al.get("tipo") or "").lower()
        if "sem risco" in risco:      # popup verde do mapa: status, não alerta
            continue
        n_total += 1
        regioes_todas.append(str(al.get("regiao_nome")
                                 or f"Região {al.get('regiao_num')}"))
        if ("inunda" in tipo or "alagamento" in tipo) and any(
                t in risco for t in config.RISCOS_ELEVADOS_POACLIMA):
            nome = al.get("regiao_nome") or f"Região {al.get('regiao_num')}"
            regioes_inundacao.append(str(nome))
    return {
        "n_total": n_total,
        "n_inundacao_risco_elevado": len(regioes_inundacao),
        "regioes_inundacao": regioes_inundacao,
        "regioes_todas": regioes_todas,
    }


def _perfil_chuva(ind: IndicadoresNumericos) -> dict:
    """
    Traduz os números de chuva em categorias, e decide o bloco
    "chove intensamente por horas/dias E as previsões indicam continuidade"
    do ALERTA por CAMINHOS ALTERNATIVOS — não por um limiar único.

    Caminhos (basta um):
      A) Já choveu MUITO  +  previsão de continuidade (mesmo moderada).
      B) Já choveu MÉDIO  +  previsão FORTE para os próximos dias.
      C) Previsão MUITO FORTE isolada (evento a caminho, ainda sem chuva).
      D) Aviso VERMELHO do INMET (grande perigo) — dispensa aritmética.

    Devolve as categorias e (ativo, motivo) já formatados para a árvore.
    """
    L = config.LIMIARES_CHUVA
    obs24 = ind.acumulado_obs_24h_mm or 0.0
    obs72 = ind.acumulado_obs_72h_mm or 0.0
    prev48 = ind.previsto_48h_mm or 0.0
    prev5d = max(ind.previsto_5d_mm or 0.0, ind.previsto_72h_mm or 0.0, prev48)
    aviso = ind.inmet_max_severidade

    # ── categorias da chuva JÁ OCORRIDA ──────────────────────
    ja_muito = (obs24 >= L["acumulado_24h_intensa"]
                or obs72 >= L["acumulado_72h_persistente"]
                or ind.dias_chuva_intensa_5d >= 2)
    ja_medio = (ja_muito
                or obs24 >= L["acumulado_24h_moderada"]
                or obs72 >= L["acumulado_72h_moderado"]
                or ind.dias_com_chuva_obs_5d >= 2)

    # ── categorias da chuva PREVISTA ─────────────────────────
    prev_forte = (prev48 >= L["previsao_48h_alerta"]
                  or prev5d >= L["previsao_5d_alerta"]
                  or aviso in ("Laranja", "Vermelho"))
    prev_continua = (prev_forte
                     or prev48 >= L["previsao_48h_mobilizacao"]
                     or prev5d >= L["previsao_5d_continuidade"]
                     or ind.dias_previsao_chuva >= L["dias_previsao_continuidade"]
                     or aviso is not None)

    def _obs_txt() -> str:
        """Uma linha só: acumulado de 96h (convenção) + fonte curta."""
        mm = ind.acumulado_obs_96h_mm or obs72
        fonte = ind.fonte_chuva_obs or "—"
        return f"{mm:.0f} mm em 96h (fonte: {fonte})"

    def _prev_linhas() -> list[str]:
        """Previsão em itens curtos, um por linha."""
        linhas = []
        if prev48:
            linhas.append(f"{prev48:.0f} mm previstos em 48h")
        if prev5d and prev5d > prev48:
            linhas.append(f"{prev5d:.0f} mm em 5 dias")
        if ind.dias_previsao_chuva:
            linhas.append(f"chuva prevista em {ind.dias_previsao_chuva} dos próximos 5 dias")
        if aviso:
            linhas.append(f"aviso do INMET vigente: {aviso}")
        return linhas or ["sem chuva relevante prevista"]

    def _bloco_prev(titulo: str) -> str:
        fonte = ind.fonte_chuva_prev or "Poaclima"
        return f"{titulo} (fonte: {fonte}):\n{_lista(_prev_linhas())}"

    ativo, caminho, motivo = False, None, ""
    if aviso == "Vermelho":
        ativo, caminho = True, "D"
        motivo = ("Aviso VERMELHO do INMET — grande perigo de chuvas intensas.\n"
                  f"Chuva registrada: {_obs_txt()}")
    elif ja_muito and prev_continua:
        ativo, caminho = True, "A"
        motivo = (f"Choveu intensamente por horas/dias: {_obs_txt()}\n\n"
                  + _bloco_prev("Além disso, a previsão indica continuidade"))
    elif ja_medio and prev_forte:
        ativo, caminho = True, "B"
        motivo = (f"Chuva acumulada relevante: {_obs_txt()}\n\n"
                  + _bloco_prev("Além disso, previsão forte para os próximos dias"))
    elif prev48 >= L["previsao_48h_alerta"] and prev5d >= L["previsao_5d_alerta"]:
        ativo, caminho = True, "C"
        motivo = (f"Chuva registrada até agora: {_obs_txt()}\n\n"
                  + _bloco_prev("Previsão de chuva forte e continuada"))
    else:
        if ja_muito and not prev_continua:
            motivo = (f"Choveu bastante: {_obs_txt()}\n"
                      "Mas a previsão não indica continuidade do padrão.")
        elif not ja_medio and not prev_continua:
            motivo = (f"Chuva abaixo do limiar: {_obs_txt()}\n"
                      "Sem previsão de chuva relevante para os próximos dias.")
        elif not ja_medio:
            motivo = (f"Chuva abaixo do limiar: {_obs_txt()}\n"
                      "A previsão isolada não é forte o bastante para o gatilho.")
        else:
            motivo = (f"Chuva acumulada: {_obs_txt()}\n"
                      "Previsão sem força suficiente para caracterizar continuidade.")

    return {
        "ja_muito": ja_muito, "ja_medio": ja_medio,
        "prev_forte": prev_forte, "prev_continua": prev_continua,
        "alerta_ativo": ativo, "alerta_caminho": caminho,
        "alerta_motivo": motivo,
        "obs_txt": _obs_txt(), "prev_txt": " · ".join(_prev_linhas()),
        # A lista crua serve a quem precisa remover um item específico antes
        # de montar o texto — hoje, o aviso do INMET na MOBILIZAÇÃO, que já
        # aparece como fator próprio e vinha repetido aqui dentro.
        "prev_linhas": _prev_linhas(),
    }


# ──────────────────────────────────────────────────────────────────────────
# CLASSIFICADOR
# ──────────────────────────────────────────────────────────────────────────
def _avaliar_regras(
    ind: IndicadoresNumericos,
    infra: InputsInfraestrutura | None = None,
    modo_estrito: bool = False,
) -> dict:
    """
    Avalia os gatilhos e retorna:
      {
        "estagio": str, "cor": str, "indice": int (0-4),
        "justificativas": [str, ...],
        "detalhes": {estagio: {"disparou": bool, "motivos": [...]}}
      }

    modo_estrito=False (padrão): blocos qualitativos sem input manual
    podem ser satisfeitos por PROXY numérico (recomendado p/ automação).
    modo_estrito=True: exige os booleanos explicitamente.
    """
    infra = infra or InputsInfraestrutura()
    L = config.LIMIARES_CHUVA
    nivel = _nivel_guaiba_efetivo(ind)   # maior leitura: ANA · Gasômetro · Cais Mauá
    tend = ind.tendencia_guaiba_48h_m or 0.0
    reg = _resumo_alertas_regionais(ind)  # alertas da Defesa Civil por região
    detalhes: dict = {}

    subindo = tend >= config.TENDENCIA_SUBIDA_RELEVANTE_M
    chuva = _perfil_chuva(ind)           # categorias + caminhos do bloco de chuva
    chuva_intensa_24h = ind.acumulado_obs_24h_mm >= L["acumulado_24h_intensa"]
    chuva_persistente = chuva["ja_muito"]
    chuva_extrema = (
        ind.acumulado_obs_72h_mm >= L["acumulado_72h_extrema"]
        or ind.acumulado_obs_7d_mm >= L["media_mensal_historica"] * L["fator_acima_media_crise"]
    )

    # ══════════════════════════════════════ 5) CRISE (roxo)
    motivos: list[str] = []
    # Bloco 1 (E): chuva muito acima da média + Guaíba subindo OU persistindo
    b1 = chuva_extrema and (
        (nivel is not None and nivel >= config.COTA_INUNDACAO_GUAIBA and (subindo or ind.dias_guaiba_acima_inundacao >= 2))
    )
    if b1:
        motivos.append(
            f"Chuva muito acima da média histórica ({ind.acumulado_obs_7d_mm:.0f} mm/7d) "
            f"E Guaíba a {nivel:.2f} m (≥ cota de inundação {config.COTA_INUNDACAO_GUAIBA} m) "
            f"{'em subida' if subindo else f'há {ind.dias_guaiba_acima_inundacao} dia(s)'}"
        )
    # Bloco 2 (E): colapso da drenagem — proxy: extravasamento severo
    proxy_b2 = (nivel is not None and nivel >= config.COTA_INUNDACAO_GUAIBA + 0.5)
    b2 = infra.colapso_drenagem_urbana or (not modo_estrito and proxy_b2)
    if b2:
        motivos.append("Colapso/risco de colapso da drenagem urbana"
                       + ("" if infra.colapso_drenagem_urbana else " (proxy: nível ≥ inundação +0,5 m)"))
    # Bloco 3 (E): infraestrutura em grande escala — proxy: b1 forte
    b3 = infra.interrupcao_infraestrutura_grande_escala or (not modo_estrito and b1 and proxy_b2)
    # Bloco 4 (E): isolamento OU abrigos OU óbitos — proxy idem
    b4 = (infra.isolamento_areas_comunidades or infra.descontrole_rede_abrigos
          or infra.obitos_pelo_evento or (not modo_estrito and b1 and proxy_b2))
    # Bloco 5 (E): impacto severo na saúde — proxy idem
    b5 = (infra.sobrecarga_sistema_saude or infra.necessidade_apoio_federal_estadual
          or (not modo_estrito and b1 and proxy_b2))
    disparou_crise = b1 and b2 and b3 and b4 and b5
    detalhes["CRISE"] = {"disparou": disparou_crise, "motivos": motivos,
        "blocos": [
            {"n": 1, "titulo": "Chuvas muito acima da média histórica", "ativo": bool(b1)},
            {"n": 2, "titulo": "Colapso OU risco de colapso da drenagem urbana", "ativo": bool(b2)},
            {"n": 3, "titulo": "Interrupção de infraestrutura em grande escala", "ativo": bool(b3)},
            {"n": 4, "titulo": "Isolamento de áreas/comunidades OU descontrole da rede de abrigos OU óbitos", "ativo": bool(b4)},
            {"n": 5, "titulo": "Impacto severo no sistema de saúde OU necessidade de apoio estadual/federal", "ativo": bool(b5)}]}
    if disparou_crise:
        return _montar_saida("CRISE", motivos, detalhes)

    # ══════════════════════════════════════ 4) SITUAÇÃO DE EMERGÊNCIA (vermelho)
    motivos = []
    # Bloco 1 (E): chuvas intensas persistentes causando inundações/deslizamentos
    varias_regioes_inundacao = (
        reg["n_inundacao_risco_elevado"] >= config.N_REGIOES_INUNDACAO_EMERGENCIA)
    b1 = (chuva_persistente and
          (infra.inundacoes_graves_ou_deslizamentos
           or (not modo_estrito and nivel is not None and nivel >= config.COTA_INUNDACAO_GUAIBA)
           or (not modo_estrito and varias_regioes_inundacao)))
    if b1:
        if varias_regioes_inundacao and not infra.inundacoes_graves_ou_deslizamentos:
            motivos.append(
                f"Defesa Civil com {reg['n_inundacao_risco_elevado']} regiões em risco "
                f"elevado de Inundação ({', '.join(reg['regioes_inundacao'][:5])}) "
                f"sob chuva persistente ({ind.acumulado_obs_72h_mm:.0f} mm/72h)")
        else:
            motivos.append(
                f"Chuvas intensas persistentes ({ind.acumulado_obs_72h_mm:.0f} mm/72h) "
                f"causando inundações (Guaíba {nivel:.2f} m ≥ cota de inundação)"
                if nivel is not None else "Chuvas intensas persistentes com inundações graves")
    # Bloco 2 (E): vias/infra DANIFICADAS OU interrupção parcial de serviços.
    # ATENÇÃO: "bloqueio de vias principais" NÃO entra aqui. No Plano ele é
    # gatilho da coluna ALERTA ("há bloqueio de vias principais e/ou
    # estratégicas"); a coluna EMERGÊNCIA exige DANO à infraestrutura
    # ("pontes e estradas podem estar danificadas"). Misturar os dois fazia
    # o painel marcar "vias ou pontes danificadas" com o Guaíba longe da
    # cota de inundação e sem nenhum dano registrado em campo.
    b2 = (infra.vias_ou_pontes_danificadas
          or infra.interrupcao_parcial_servicos_essenciais
          or (not modo_estrito and nivel is not None
              and nivel >= config.COTA_INUNDACAO_GUAIBA))
    if infra.vias_ou_pontes_danificadas or infra.interrupcao_parcial_servicos_essenciais:
        motivo_e2 = "Dano em vias/infraestrutura OU interrupção de serviços essenciais (confirmado em campo)"
        motivos.append(motivo_e2)
    elif b2:
        motivo_e2 = (f"proxy: Guaíba a {nivel:.2f} m, acima da cota de inundação "
                     f"({config.COTA_INUNDACAO_GUAIBA} m)")
    else:
        motivo_e2 = ("sem dano de infraestrutura confirmado e Guaíba abaixo da "
                     "cota de inundação")
    # Bloco 3 (E): desabrigados OU óbitos — proxy: transbordamento
    b3 = (infra.aumento_significativo_desabrigados or infra.obitos_pelo_evento
          or (not modo_estrito and nivel is not None
              and nivel >= config.COTA_INUNDACAO_GUAIBA))
    # Bloco 4 (E): saúde acometida OU risco de desabastecimento — proxy idem
    b4 = (infra.servicos_saude_interrompidos or infra.risco_alto_desabastecimento
          or (not modo_estrito and nivel is not None
              and nivel >= config.COTA_INUNDACAO_GUAIBA))
    disparou_emerg = b1 and b2 and b3 and b4
    if disparou_emerg and len(motivos) == 1:
        motivos.append("Gatilhos de infraestrutura satisfeitos por proxy (transbordamento do Guaíba)")
    detalhes["SITUAÇÃO DE EMERGÊNCIA"] = {"disparou": disparou_emerg, "motivos": motivos,
        "blocos": [
            {"n": 1, "titulo": "Chuvas intensas persistentes causando inundações graves OU deslizamentos",
             "ativo": bool(b1),
             "motivo": (motivos[0] if b1 and motivos else
                        (f"Chuva persistente: {'sim' if chuva_persistente else 'não'}"
                         f" — {chuva['obs_txt']}\n"
                         "Nenhuma inundação grave ou deslizamento registrado."))},
            {"n": 2, "titulo": "Vias ou pontes danificadas OU interrupção parcial de serviços essenciais",
             "ativo": bool(b2), "motivo": motivo_e2},
            {"n": 3, "titulo": "Aumento de desabrigados/desalojados OU óbitos pelo evento",
             "ativo": bool(b3),
             "motivo": ("confirmado em campo" if (infra.aumento_significativo_desabrigados
                                                  or infra.obitos_pelo_evento)
                        else ("proxy: Guaíba acima da cota de inundação" if b3
                              else "nenhum registro confirmado"))},
            {"n": 4, "titulo": "Serviços de saúde interrompidos OU risco alto de desabastecimento",
             "ativo": bool(b4),
             "motivo": ("confirmado em campo" if (infra.servicos_saude_interrompidos
                                                  or infra.risco_alto_desabastecimento)
                        else ("proxy: Guaíba acima da cota de inundação" if b4
                              else "nenhum registro confirmado"))}]}
    if disparou_emerg:
        return _montar_saida("SITUAÇÃO DE EMERGÊNCIA", motivos, detalhes)

    # ══════════════════════════════════════ 3) ALERTA (laranja)
    motivos = []
    # Bloco 1 (E): chove intensamente por horas/dias na RM e previsão de continuidade
    # → agora por CAMINHOS ALTERNATIVOS (ver _perfil_chuva), e não por um
    #   limiar único que só fechava em evento recordista.
    b1 = chuva["alerta_ativo"]
    motivo_b1 = chuva["alerta_motivo"]
    if b1:
        motivos.append(motivo_b1)
    # Bloco 2 (E): Guaíba em cota de ALERTA  OU afluentes em alerta subindo
    #              OU córregos/encostas  OU Defesa Civil c/ risco elevado de inundação
    cond_guaiba = nivel is not None and nivel >= config.COTA_ALERTA_GUAIBA
    cond_afl = _afluente_atingiu(ind, "alerta") and (subindo or _afluente_subindo(ind))
    cond_corregos, motivo_corregos = _corregos_subindo(ind)
    cond_regional = reg["n_inundacao_risco_elevado"] >= 1
    b2 = cond_guaiba or cond_afl or cond_corregos or cond_regional
    if cond_guaiba:
        motivos.append(f"Guaíba em Cota de Alerta de Inundação "
                       f"({nivel:.2f} m ≥ {config.COTA_ALERTA_GUAIBA} m)")
    elif cond_afl:
        quais_afl = _rios_em_cota(ind, None, "alerta")
        motivos.append("Afluente em cota de alerta, com tendência de alta nas "
                       "próximas 48h\n" + _lista(quais_afl))
    elif cond_corregos and motivo_corregos:
        motivos.append(motivo_corregos)
    elif cond_regional:
        motivos.append(
            f"Defesa Civil (Poaclima) com alerta de risco elevado de Inundação em "
            f"{reg['n_inundacao_risco_elevado']} região(ões): "
            f"{', '.join(reg['regioes_inundacao'][:5])}")
    # Bloco 3 (E): famílias/abrigos/vias/saúde (OU entre eles) — proxy: b1 E b2 fortes
    b3 = (infra.familias_deixando_casas or infra.aumento_demanda_abrigo
          or infra.abrigos_temporarios_instalados or infra.bloqueio_vias_principais
          or infra.aumento_demanda_saude_clima
          or (not modo_estrito and b1 and b2))
    disparou_alerta = b1 and b2 and b3
    motivo_b2 = next((m for m in motivos if m is not motivo_b1), "") if b2 else \
        ("Nenhum rio atingiu cota de alerta e a Defesa Civil não tem "
         "região em risco elevado de inundação.")
    _conf = [config.ROTULOS_GATILHOS[c] for c in
             ("familias_deixando_casas", "aumento_demanda_abrigo",
              "abrigos_temporarios_instalados", "bloqueio_vias_principais",
              "aumento_demanda_saude_clima") if getattr(infra, c, False)]
    motivo_b3 = ("Confirmado em campo pela Defesa Civil/SMS:\n"
                 + _lista(_conf) if _conf
                 else ("Satisfeito por proxy: blocos 1 e 2 ativos." if b3
                       else "Nenhum gatilho de campo confirmado."))
    detalhes["ALERTA"] = {"disparou": disparou_alerta, "motivos": motivos,
        "blocos": [
            {"n": 1, "titulo": "Chuva intensa por horas/dias com previsão de continuidade",
             "ativo": bool(b1), "motivo": motivo_b1,
             "caminho": chuva["alerta_caminho"]},
            {"n": 2, "titulo": "Guaíba em cota de alerta OU afluentes/córregos subindo OU risco de inundação",
             "ativo": bool(b2), "motivo": motivo_b2},
            {"n": 3, "titulo": "Famílias deixando casas OU demanda por abrigo OU bloqueio de vias OU demanda na saúde",
             "ativo": bool(b3), "motivo": motivo_b3}]}
    if disparou_alerta:
        return _montar_saida("ALERTA", motivos, detalhes)

    # ══════════════════════════════════════ 2) MOBILIZAÇÃO (amarelo)
    motivos = []
    # Bloco 1: previsão de chuvas mais intensas / avisos vigentes
    b1 = (chuva["prev_continua"] or chuva["ja_muito"]
          or ind.inmet_max_severidade is not None
          or ind.poaclima_alerta is not None
          or reg["n_total"] >= 1)
    if b1:
        fatores = []
        # O aviso do INMET tem fator próprio logo abaixo. Se ele também
        # ficasse na lista da previsão, a mesma informação apareceria duas
        # vezes no mesmo bloco — uma como item, outra como subitem.
        prev_itens = [l for l in chuva.get("prev_linhas", [])
                      if not l.lower().startswith("aviso do inmet")]
        if chuva["prev_continua"] and prev_itens:
            fatores.append("previsão de chuvas mais intensas ("
                           + " · ".join(prev_itens) + ")")
        if chuva["ja_muito"]:
            fatores.append(f"chuva forte já registrada ({chuva['obs_txt']})")
        if ind.inmet_max_severidade:
            fatores.append(f"aviso INMET vigente ({ind.inmet_max_severidade})")
        if reg["n_total"]:
            # Só a CONTAGEM. A lista de regiões cabia em cinco nomes e a
            # cidade tem dezessete: o bloco ficava com uma enumeração
            # truncada, que engorda a caixa e ainda induz a ler "só essas".
            # Quais regiões estão sob alerta é o que a grade do Poaclima,
            # logo abaixo, mostra inteira e com o grau de cada uma.
            fatores.append(f"{reg['n_total']} alerta(s) vigente(s) da Defesa "
                           f"Civil (ver grade por região)")
        if not fatores and ind.poaclima_alerta:
            fatores.append(f"alerta Poaclima vigente ({ind.poaclima_alerta})")
        motivos.append("Avisos/previsão em vigor: " + "; ".join(fatores))
    # Bloco 2: tendência de aumento dos rios / cota de ATENÇÃO  OU  RM em alerta
    cond_riacho_atencao = bool(_cota_atingida(_refs_riacho(),
                                              ind.poaclima_riacho_ipiranga_m))
    # Uma lista só, montada uma vez: Guaíba, Ipiranga e todos os afluentes que
    # passaram pelo menos a cota de atenção (ou a menor cota publicada da
    # própria régua, quando não há atenção cadastrada).
    rios_atencao = _rios_em_cota(ind, nivel, "atencao")
    cond_atencao = bool(rios_atencao)
    cond_alerta_inundacao = reg["n_inundacao_risco_elevado"] >= 1
    b2 = ((subindo and cond_atencao) or cond_atencao or subindo
          or _afluente_subindo(ind) or ind.metropole_em_alerta
          or cond_alerta_inundacao)
    if cond_atencao:
        motivos.append("Rio(s) na Cota de Atenção ou acima: "
                       + "; ".join(rios_atencao))
    elif subindo or _afluente_subindo(ind):
        motivos.append(f"Tendência de aumento dos rios que deságuam no Guaíba (+{tend:.2f} m/48h)")
    elif ind.metropole_em_alerta:
        motivos.append("Cidade(s) da Região Metropolitana já em estágio de alerta")
    elif cond_alerta_inundacao:
        regs = ", ".join(reg.get("regioes_inundacao", [])[:5])
        motivos.append("Região(ões) da cidade já em alerta de risco de "
                       f"inundação pela Defesa Civil: {regs}")
    disparou_mob = b1 and b2
    detalhes["MOBILIZAÇÃO"] = {"disparou": disparou_mob, "motivos": motivos,
        "blocos": [
            {"n": 1, "titulo": "Previsão de chuvas mais intensas OU avisos meteorológicos vigentes",
             "ativo": bool(b1),
             "motivo": (motivos[0] if b1 and motivos
                        else f"sem previsão relevante ({chuva['prev_txt']})")},
            {"n": 2, "titulo": "Rios em cota de atenção OU em elevação OU região da RM já em alerta",
             "ativo": bool(b2),
             "motivo": (motivos[-1] if b2 and motivos
                        else "rios abaixo da cota de atenção e sem tendência de subida")}]}
    if disparou_mob:
        return _montar_saida("MOBILIZAÇÃO", motivos, detalhes)

    # ══════════════════════════════════════ 1) NORMALIDADE (verde)
    motivos = ["Condições climáticas típicas para a estação",
               "Principais vias sem bloqueios"]
    # Justificativa hidrológica honesta + observações de quase-gatilho:
    quase = []
    if cond_atencao:
        quase.append("rio(s) na Cota de Atenção ou acima: "
                     + "; ".join(rios_atencao))
    if subindo:
        quase.append(f"Guaíba em subida (+{tend:.2f} m/48h)")
    elif _afluente_subindo(ind):
        quase.append("afluente(s) em tendência de subida")

    if quase:
        motivos.append(
            "OBSERVAÇÃO — monitorar: " + "; ".join(quase[:4]) +
            ". Sem previsão de chuvas intensas "
            f"({ind.previsto_48h_mm:.0f} mm/48h), o gatilho de MOBILIZAÇÃO "
            "(bloco de previsão) não fecha.")
    else:
        motivos.append("Elevação das bacias próximas não configura risco ou ameaça")
    # Sem NENHUM dado de nível de rio não é possível afirmar que "a elevação
    # das águas não configura risco" (exigência da coluna NORMALIDADE).
    sem_dados_rios = (not ind.afluentes) and nivel is None
    hidro_incompleta = (not ind.afluentes) or nivel is None
    if hidro_incompleta:
        motivos.insert(0,
            "⚠ Dados de nível dos rios incompletos nesta coleta — "
            "não é possível confirmar a normalidade hidrológica. "
            "Consulte os canais oficiais da Defesa Civil.")

    detalhes["NORMALIDADE"] = {"disparou": True, "motivos": motivos}
    return _montar_saida("NORMALIDADE", motivos, detalhes,
                         dados_insuficientes=hidro_incompleta or sem_dados_rios)


def gatilhos_ativos(infra: InputsInfraestrutura | None) -> list[tuple[str, str]]:
    """Lista [(campo, rótulo)] dos gatilhos marcados como confirmados."""
    if infra is None:
        return []
    ativos = []
    for campo, rotulo in config.ROTULOS_GATILHOS.items():
        if getattr(infra, campo, False):
            ativos.append((campo, rotulo))
    return ativos


def classificar_estagio(
    ind: IndicadoresNumericos,
    infra: InputsInfraestrutura | None = None,
    modo_estrito: bool = False,
) -> dict:
    """
    Classificação final = APENAS as regras E/OU do Plano (item 5.1).

    Os gatilhos confirmados em campo NÃO elevam o estágio por si sós. Eles
    já entram nas regras onde o Plano os escreve — bloco 3 do ALERTA,
    blocos 2/3/4 da EMERGÊNCIA, blocos 2/4/5 da CRISE — sempre ligados por
    E aos blocos de chuva e de nível dos rios. Se esses outros blocos não
    fecham, a coluna não fecha, e o estágio é o mais grave que realmente
    fechou: o painel desce sozinho quando o evento passa.

    A antiga "regra de piso" fazia o contrário — um gatilho marcado no txt
    bastava para segurar o painel em ALERTA com tempo firme e rios baixos.
    Ela fica desligada em config.PISO_POR_GATILHO_MANUAL; o parâmetro
    continua existindo para quem quiser reativá-la conscientemente.

    Gatilhos confirmados acima do estágio calculado viram uma OBSERVAÇÃO
    explícita nas justificativas — informação para a equipe, não decisão.
    """
    resultado = _avaliar_regras(ind, infra=infra, modo_estrito=modo_estrito)

    ativos = gatilhos_ativos(infra)
    if not ativos:
        return resultado

    resultado = dict(resultado)
    justificativas = list(resultado["justificativas"])
    justificativas.append(
        "⚙ Gatilhos confirmados em campo: " + "; ".join(r for _, r in ativos))

    # Gatilhos de coluna mais grave que o estágio calculado: dizer em voz
    # alta que eles NÃO mudaram o estágio, e por quê. Sem isso, quem marcou
    # o txt fica sem entender por que o painel não subiu.
    acima = [(config.ESTAGIOS.index(config.PISO_GATILHOS[campo]), rotulo,
              config.PISO_GATILHOS[campo])
             for campo, rotulo in ativos
             if config.PISO_GATILHOS.get(campo)
             and config.ESTAGIOS.index(config.PISO_GATILHOS[campo]) > resultado["indice"]]

    if acima and not config.PISO_POR_GATILHO_MANUAL:
        idx_max = max(i for i, _, _ in acima)
        coluna = config.ESTAGIOS[idx_max]
        quais = "; ".join(r for i, r, _ in acima if i == idx_max)
        justificativas.append(
            f"ℹ Há gatilho(s) da coluna {coluna} confirmado(s) em campo "
            f"({quais}), mas o estágio permanece {resultado['estagio']}: no "
            f"Plano esses gatilhos são apenas UMA das alternativas de um dos "
            f"blocos da coluna {coluna}, e os demais blocos (chuva e nível "
            f"dos rios) não estão fechando.")

    if acima and config.PISO_POR_GATILHO_MANUAL:
        # Comportamento legado, só se reativado no config.
        idx_max = max(i for i, _, _ in acima)
        estagio_final = config.ESTAGIOS[idx_max]
        responsaveis = [r for i, r, _ in acima if i == idx_max]
        justificativas.append(
            f"⚑ Estágio elevado de {resultado['estagio']} para {estagio_final} "
            f"pela REGRA DE PISO: gatilho(s) da coluna {estagio_final} do Plano "
            f"confirmado(s) em campo — {'; '.join(responsaveis)}")
        detalhes = dict(resultado["detalhes"])
        detalhes["PISO_GATILHOS"] = {"disparou": True, "motivos": responsaveis}
        return _montar_saida(estagio_final, justificativas, detalhes)

    resultado["justificativas"] = justificativas
    return resultado


def ler_gatilhos_txt(caminho=None) -> InputsInfraestrutura:
    """
    Lê `gatilhos_manuais.txt` (um gatilho por linha: campo = ok|nao).
    Aceita como CONFIRMADO: ok, sim, s, true, 1, x (qualquer caixa).
    Se o arquivo não existir, cria o modelo com todos = nao.
    """
    caminho = caminho or config.GATILHOS_TXT
    if not caminho.exists():
        try:
            criar_modelo_gatilhos_txt(caminho)
        except OSError as exc:      # container com FS somente-leitura
            print(f"[Gatilhos] Modelo não criado ({exc}); seguindo só com env vars.")

    positivos = {"ok", "sim", "s", "true", "1", "x", "yes"}
    valores: dict[str, bool] = {}
    texto = caminho.read_text(encoding="utf-8") if caminho.exists() else ""
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        campo, _, valor = linha.partition("=")
        campo = campo.strip().lower()
        if campo in config.ROTULOS_GATILHOS:
            valores[campo] = valor.strip().lower() in positivos
        else:
            print(f"[Gatilhos] Campo desconhecido no txt (ignorado): {campo}")

    # Variável de ambiente GATILHOS_ATIVOS tem prioridade (útil no Render:
    # permite confirmar um gatilho pelo painel do Render, sem git push).
    # Ex.: GATILHOS_ATIVOS="bloqueio_vias_principais,obitos_pelo_evento"
    import os as _os
    env_gatilhos = _os.environ.get("GATILHOS_ATIVOS", "").strip()
    if env_gatilhos:
        for campo in env_gatilhos.replace(";", ",").split(","):
            campo = campo.strip().lower()
            if campo in config.ROTULOS_GATILHOS:
                valores[campo] = True
            elif campo:
                print(f"[Gatilhos] Campo desconhecido em GATILHOS_ATIVOS: {campo}")

    infra = InputsInfraestrutura(**valores)
    ativos = gatilhos_ativos(infra)
    if ativos:
        print(f"[Gatilhos] {len(ativos)} gatilho(s) confirmado(s): "
              + "; ".join(r for _, r in ativos))
    return infra


def criar_modelo_gatilhos_txt(caminho=None):
    """Gera o gatilhos_manuais.txt modelo (todos = nao) com instruções."""
    caminho = caminho or config.GATILHOS_TXT
    linhas = [
        "# ============================================================",
        "# GATILHOS MANUAIS — Plano de Contingência (item 5.1)",
        "# Preenchido pela Defesa Civil/SMS quando o evento é CONFIRMADO.",
        "#",
        "# Como usar: troque 'nao' por 'ok' no gatilho confirmado e rode",
        "# a atualização (célula 4 ou botão do dashboard).",
        "#",
        "# O gatilho NÃO define o estágio sozinho: ele entra como UMA das",
        "# alternativas do bloco em que o Plano o escreve, e esse bloco é",
        "# ligado por E aos blocos de chuva e de nível dos rios. Se os",
        "# outros blocos não fecham, o estágio não sobe — e volta a descer",
        "# sozinho quando o evento passa.",
        "# ============================================================",
        "",
    ]
    piso_por_grupo = {"ALERTA": [], "SITUAÇÃO DE EMERGÊNCIA": [], "CRISE": []}
    for campo, rotulo in config.ROTULOS_GATILHOS.items():
        piso_por_grupo[config.PISO_GATILHOS[campo]].append((campo, rotulo))
    for grupo, itens in piso_por_grupo.items():
        linhas.append(f"# ── Coluna {grupo} " + "─" * max(1, 40 - len(grupo)))
        for campo, rotulo in itens:
            linhas.append(f"# {rotulo}")
            linhas.append(f"{campo} = nao")
            linhas.append("")
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    print(f"[Gatilhos] Modelo criado: {caminho}")


def _montar_saida(estagio: str, motivos: list[str], detalhes: dict,
                  dados_insuficientes: bool = False) -> dict:
    saida = {
        "estagio": estagio,
        "blocos_por_estagio": {e: d.get("blocos", [])
                               for e, d in (detalhes or {}).items()
                               if isinstance(d, dict)},
        "indice": config.ESTAGIOS.index(estagio),
        "cor": config.CORES_ESTAGIOS[estagio],
        "justificativas": motivos,
        "detalhes": detalhes,
    }
    if dados_insuficientes:
        # Nunca exibir "verde tranquilo" quando faltam dados essenciais:
        # o painel passa a mostrar um estado neutro e explícito.
        saida["dados_insuficientes"] = True
        saida["rotulo"] = "DADOS INSUFICIENTES"
        saida["cor"] = "#4A5561"
    return saida


# ──────────────────────────────────────────────────────────────────────────
# ADAPTADOR: dados brutos da coleta → IndicadoresNumericos
# ──────────────────────────────────────────────────────────────────────────
def indicadores_dos_brutos(brutos: dict) -> IndicadoresNumericos:
    """Converte a saída de `consolidacao.coletar_tudo()` em IndicadoresNumericos."""
    resumo_rios = brutos.get("resumo_rios", {})
    guaiba = resumo_rios.get("Guaiba_PortoAlegre_CaisMaua", {})
    afluentes = {n: r for n, r in resumo_rios.items()
                 if n != "Guaiba_PortoAlegre_CaisMaua"}
    meteo = brutos.get("meteo", {}).get("resumo", {}) or {}

    # persistência acima da cota de inundação (a partir da série)
    dias_acima = 0
    serie = brutos.get("rios", {}).get("Guaiba_PortoAlegre_CaisMaua")
    if serie is not None and not serie.empty and "nivel_m" in serie:
        diario = (serie.dropna(subset=["nivel_m"])
                       .set_index("datahora")["nivel_m"].resample("D").max())
        for v in reversed(diario.tolist()):
            if v is not None and v >= config.COTA_INUNDACAO_GUAIBA:
                dias_acima += 1
            else:
                break

    niveis_poa = (brutos.get("poaclima", {}) or {}).get("niveis") or {}

    # ── Fontes preferenciais de chuva (alinham o painel com a Defesa Civil) ──
    # Observado: estação automática do INMET em POA (pluviômetro local).
    # Previsto : Poaclima/Catavento (a mesma previsão que a DC de POA exibe).
    # O Open-Meteo (modelo global) fica como reserva quando faltarem.
    # ── Prioridade das fontes de CHUVA (decisão de produto 26/07) ──
    #   observada: Poaclima (Defesa Civil) → INMET → ANA → Open-Meteo
    #   prevista : Poaclima/Catavento → Open-Meteo
    # O Open-Meteo é um modelo global: só entra se nada local responder.
    # ── OBSERVADA: vem pronta e já auditada de coleta/chuva_observada.py ──
    co = brutos.get("chuva_obs") or {}
    if co.get("ok"):
        obs_24h = co.get("acumulado_24h_mm") or 0.0
        obs_72h = co.get("acumulado_72h_mm") or 0.0
        obs_96h = co.get("acumulado_96h_mm") or obs_72h
        obs_5d = co.get("acumulado_5d_mm") or obs_96h
        obs_7d = co.get("acumulado_7d_mm") or 0.0
        fonte_obs = co.get("fonte_curta") or co.get("fonte") or "—"
        dias_obs = co.get("dias_com_chuva_5d", 0)
        dias_int = co.get("dias_chuva_intensa_5d", 0)
        qualidade = (co.get("qualidade") or {}).get("motivo")
    else:
        obs_24h = meteo.get("acumulado_obs_24h_mm", 0.0)
        obs_72h = meteo.get("acumulado_obs_72h_mm", 0.0)
        obs_96h = obs_72h
        obs_5d = meteo.get("acumulado_obs_7d_mm", 0.0)
        obs_7d = meteo.get("acumulado_obs_7d_mm", 0.0)
        fonte_obs, dias_obs, qualidade = "Open-Meteo (modelo global)", 0, None
        dias_int = meteo.get("dias_chuva_intensa_5d", 0)

    # ── PREVISTA: Poaclima/Catavento (a mesma da Defesa Civil) → Open-Meteo ──
    # O Plano exige "previsões indicam CONTINUIDADE do padrão", então além do
    # volume de 48h calculamos 72h, 5 dias e quantos dias terão chuva.
    pp = brutos.get("previsao_poaclima") or {}
    previsto48 = meteo.get("previsto_48h_mm", 0.0) or 0.0
    previsto72 = meteo.get("previsto_72h_mm", 0.0) or 0.0
    previsto5d = 0.0
    dias_prev = 0
    fonte_prev = "Open-Meteo"

    limiar_dia = config.LIMIARES_CHUVA["dia_com_chuva_relevante"]
    if pp.get("ok") and pp.get("dias"):
        import datetime as _dt
        hoje = _dt.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        futuros = sorted((d for d in pp["dias"] if d.get("data") and d["data"] >= hoje),
                         key=lambda d: d["data"])
        vals = [float(d.get("precipitacao_total_mm") or 0.0) for d in futuros]
        previsto48 = sum(vals[:2])
        previsto72 = sum(vals[:3])
        previsto5d = sum(vals[:5])
        dias_prev = sum(1 for v in vals[:5] if v >= limiar_dia)
        fonte_prev = "Poaclima/Catavento"
    else:
        diaria = brutos.get("meteo", {}).get("diaria")
        if diaria is not None and not diaria.empty:
            import pandas as _pd
            hoje = _pd.Timestamp.now().normalize()
            fut = diaria[diaria["data"] >= hoje].head(5)
            previsto5d = float(fut["precipitacao_total_mm"].sum())
            dias_prev = int((fut["precipitacao_total_mm"] >= limiar_dia).sum())

    print(f"[CHUVA] observada: {fonte_obs} "
          f"({obs_24h:.0f} mm/24h · {obs_72h:.0f} mm/72h · {obs_7d:.0f} mm/7d)")
    print(f"[CHUVA] prevista : {fonte_prev} "
          f"({previsto48:.0f} mm/48h · {previsto5d:.0f} mm/5d · "
          f"{dias_prev} dia(s) com chuva)")
    previsto = previsto48

    return IndicadoresNumericos(
        nivel_guaiba_m=guaiba.get("nivel_atual_m"),
        tendencia_guaiba_48h_m=guaiba.get("tendencia_48h_m"),
        dias_guaiba_acima_inundacao=dias_acima,
        afluentes=afluentes,
        acumulado_obs_24h_mm=obs_24h or 0.0,
        acumulado_obs_72h_mm=obs_72h or 0.0,
        acumulado_obs_96h_mm=obs_96h or 0.0,
        acumulado_obs_5d_mm=obs_5d or 0.0,
        acumulado_obs_7d_mm=obs_7d or 0.0,
        previsto_48h_mm=previsto or 0.0,
        previsto_72h_mm=previsto72 or 0.0,
        previsto_5d_mm=previsto5d or 0.0,
        dias_previsao_chuva=dias_prev,
        dias_com_chuva_obs_5d=dias_obs,
        fonte_chuva_obs=fonte_obs,
        fonte_chuva_prev=fonte_prev,
        qualidade_chuva_obs=qualidade,
        dias_chuva_intensa_5d=dias_int,
        inmet_max_severidade=brutos.get("inmet", {}).get("max_severidade"),
        poaclima_alerta=brutos.get("poaclima", {}).get("alerta_vigente"),
        poaclima_gasometro_m=niveis_poa.get("usina_gasometro_m"),
        poaclima_cais_maua_m=niveis_poa.get("cais_maua_m"),
        poaclima_riacho_ipiranga_m=niveis_poa.get("riacho_ipiranga_m"),
        alertas_regionais=(brutos.get("poaclima", {}) or {}).get("alertas_regionais") or [],
    )


def indicadores_de_dict(d: dict) -> IndicadoresNumericos:
    """
    Reconstrói IndicadoresNumericos a partir de snapshot["indicadores"]
    (dict serializado). Usado pelo dashboard para RECLASSIFICAR na hora,
    sem recoletar nada.
    """
    import dataclasses
    campos = {f.name for f in dataclasses.fields(IndicadoresNumericos)}
    limpo = {}
    for k, v in (d or {}).items():
        if k not in campos:
            continue
        if k == "afluentes":
            limpo[k] = {nome: dict(res) for nome, res in (v or {}).items()}
        elif k == "alertas_regionais":
            limpo[k] = list(v or [])
        else:
            limpo[k] = v
    return IndicadoresNumericos(**limpo)


if __name__ == "__main__":
    # Cenário de teste: maio/2024 simulado
    ind = IndicadoresNumericos(
        nivel_guaiba_m=5.30, tendencia_guaiba_48h_m=0.6,
        dias_guaiba_acima_inundacao=3,
        acumulado_obs_24h_mm=90, acumulado_obs_72h_mm=300,
        acumulado_obs_7d_mm=420, previsto_48h_mm=120,
        dias_chuva_intensa_5d=4, inmet_max_severidade="Vermelho",
    )
    import json
    saida = classificar_estagio(ind)
    print(json.dumps({k: v for k, v in saida.items() if k != "detalhes"},
                     indent=2, ensure_ascii=False))
