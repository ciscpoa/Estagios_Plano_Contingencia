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
    acumulado_obs_7d_mm: float = 0.0
    previsto_48h_mm: float = 0.0
    dias_chuva_intensa_5d: int = 0

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
def _nome(chave: str) -> str:
    """Nome de exibição da estação (sem underlines)."""
    return config.NOMES_EXIBICAO.get(chave, chave.replace("_", " "))


def _nivel_de(dados: dict) -> float | None:
    """Nível de um resumo de estação (aceita 'nivel_m' ou 'nivel_atual_m')."""
    v = dados.get("nivel_m")
    return v if v is not None else dados.get("nivel_atual_m")


def _afluente_atingiu(ind: IndicadoresNumericos, cota: str) -> bool:
    """True se algum afluente atingiu a cota ('atencao'/'alerta'/'inundacao')."""
    for nome, dados in ind.afluentes.items():
        ref = (config.COTAS_AFLUENTES.get(nome) or {}).get(cota)
        nivel = _nivel_de(dados)
        if ref is not None and nivel is not None and nivel >= ref:
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
    chuva_intensa_24h = ind.acumulado_obs_24h_mm >= L["acumulado_24h_intensa"]
    chuva_persistente = (ind.acumulado_obs_72h_mm >= L["acumulado_72h_persistente"]
                         or ind.dias_chuva_intensa_5d >= 2)
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
    detalhes["CRISE"] = {"disparou": disparou_crise, "motivos": motivos}
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
    # Bloco 2 (E): vias/infra danificadas OU interrupção parcial de serviços
    b2 = (infra.vias_ou_pontes_danificadas or infra.interrupcao_parcial_servicos_essenciais
          or infra.bloqueio_vias_principais
          or (not modo_estrito and nivel is not None
              and nivel >= config.COTA_INUNDACAO_GUAIBA))
    if b2 and (infra.vias_ou_pontes_danificadas or infra.interrupcao_parcial_servicos_essenciais):
        motivos.append("Interrupção em vias/infraestrutura OU serviços essenciais")
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
    detalhes["SITUAÇÃO DE EMERGÊNCIA"] = {"disparou": disparou_emerg, "motivos": motivos}
    if disparou_emerg:
        return _montar_saida("SITUAÇÃO DE EMERGÊNCIA", motivos, detalhes)

    # ══════════════════════════════════════ 3) ALERTA (laranja)
    motivos = []
    # Bloco 1 (E): chove intensamente por horas/dias na RM e previsão de continuidade
    b1 = ((chuva_intensa_24h or chuva_persistente
           or ind.inmet_max_severidade in ("Laranja", "Vermelho"))
          and (ind.previsto_48h_mm >= L["previsao_48h_mobilizacao"]
               or ind.inmet_max_severidade in ("Laranja", "Vermelho")))
    if b1:
        motivos.append(
            f"Chuva intensa na RM ({ind.acumulado_obs_24h_mm:.0f} mm/24h; "
            f"aviso INMET: {ind.inmet_max_severidade or '—'}) com previsão de continuidade "
            f"({ind.previsto_48h_mm:.0f} mm/48h)")
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
        motivos.append("Afluente(s) em cota de alerta com tendência de alta nas próximas 48h")
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
    detalhes["ALERTA"] = {"disparou": disparou_alerta, "motivos": motivos}
    if disparou_alerta:
        return _montar_saida("ALERTA", motivos, detalhes)

    # ══════════════════════════════════════ 2) MOBILIZAÇÃO (amarelo)
    motivos = []
    # Bloco 1: previsão de chuvas mais intensas / avisos vigentes
    b1 = (ind.previsto_48h_mm >= L["previsao_48h_mobilizacao"]
          or ind.inmet_max_severidade is not None
          or ind.poaclima_alerta is not None
          or reg["n_total"] >= 1)
    if b1:
        fatores = []
        if ind.previsto_48h_mm >= L["previsao_48h_mobilizacao"]:
            fatores.append(f"previsão de chuvas mais intensas "
                           f"({ind.previsto_48h_mm:.0f} mm/48h)")
        if ind.inmet_max_severidade:
            fatores.append(f"aviso INMET vigente ({ind.inmet_max_severidade})")
        if reg["n_total"]:
            nomes = ", ".join(reg.get("regioes_todas", [])[:5])
            fatores.append(f"{reg['n_total']} alerta(s) vigente(s) da Defesa "
                           f"Civil" + (f" — regiões: {nomes}" if nomes else ""))
        if not fatores and ind.poaclima_alerta:
            fatores.append(f"alerta Poaclima vigente ({ind.poaclima_alerta})")
        motivos.append("Avisos/previsão em vigor: " + "; ".join(fatores))
    # Bloco 2: tendência de aumento dos rios / cota de ATENÇÃO  OU  RM em alerta
    cond_riacho_atencao = (ind.poaclima_riacho_ipiranga_m is not None
                           and config.COTA_ATENCAO_RIACHO_IPIRANGA is not None
                           and ind.poaclima_riacho_ipiranga_m >= config.COTA_ATENCAO_RIACHO_IPIRANGA)
    cond_atencao = ((nivel is not None and nivel >= config.COTA_ATENCAO_GUAIBA)
                    or _afluente_atingiu(ind, "atencao") or cond_riacho_atencao)
    cond_alerta_inundacao = reg["n_inundacao_risco_elevado"] >= 1
    b2 = ((subindo and cond_atencao) or cond_atencao or subindo
          or _afluente_subindo(ind) or ind.metropole_em_alerta
          or cond_alerta_inundacao)
    if cond_atencao:
        quais = []
        if nivel is not None and nivel >= config.COTA_ATENCAO_GUAIBA:
            quais.append(f"Guaíba {nivel:.2f} m")
        for nome_afl, dados_afl in ind.afluentes.items():
            ref_a = (config.COTAS_AFLUENTES.get(nome_afl) or {}).get("atencao")
            nv_a = _nivel_de(dados_afl)
            if ref_a is not None and nv_a is not None and nv_a >= ref_a:
                quais.append(f"{_nome(nome_afl)} {nv_a:.2f} m (≥ {ref_a:.2f})")
        if cond_riacho_atencao:
            quais.append(f"Riacho Ipiranga {ind.poaclima_riacho_ipiranga_m:.2f} m")
        motivos.append("Rio(s) atingindo a Cota de Atenção: " + "; ".join(quais[:4]))
    elif subindo or _afluente_subindo(ind):
        motivos.append(f"Tendência de aumento dos rios que deságuam no Guaíba (+{tend:.2f} m/48h)")
    elif ind.metropole_em_alerta:
        motivos.append("Cidade(s) da Região Metropolitana já em estágio de alerta")
    elif cond_alerta_inundacao:
        regs = ", ".join(reg.get("regioes_inundacao", [])[:5])
        motivos.append("Região(ões) da cidade já em alerta de risco de "
                       f"inundação pela Defesa Civil: {regs}")
    disparou_mob = b1 and b2
    detalhes["MOBILIZAÇÃO"] = {"disparou": disparou_mob, "motivos": motivos}
    if disparou_mob:
        return _montar_saida("MOBILIZAÇÃO", motivos, detalhes)

    # ══════════════════════════════════════ 1) NORMALIDADE (verde)
    motivos = ["Condições climáticas típicas para a estação",
               "Principais vias sem bloqueios"]
    # Justificativa hidrológica honesta + observações de quase-gatilho:
    quase = []
    if cond_atencao:
        quase.append("rio(s) na Cota de Atenção"
                     + (f" (Guaíba {nivel:.2f} m)" if nivel is not None
                        and nivel >= config.COTA_ATENCAO_GUAIBA else ""))
        for nome, dados in ind.afluentes.items():
            ref = (config.COTAS_AFLUENTES.get(nome) or {}).get("atencao")
            nv = _nivel_de(dados)
            if ref is not None and nv is not None and nv >= ref:
                quase.append(f"{_nome(nome)} em {nv:.2f} m (≥ atenção {ref:.2f} m)")
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
    Classificação final = regras E/OU do Plano + REGRA DE PISO:
    um gatilho qualitativo CONFIRMADO em campo eleva o estágio, no mínimo,
    até a coluna do Plano (item 5.1) onde esse gatilho está escrito —
    o evento confirmado é evidência direta daquela severidade, ainda que
    os blocos meteorológicos não tenham fechado.
    Desativável em config.PISO_POR_GATILHO_MANUAL.
    """
    resultado = _avaliar_regras(ind, infra=infra, modo_estrito=modo_estrito)

    if not config.PISO_POR_GATILHO_MANUAL or infra is None:
        return resultado

    ativos = gatilhos_ativos(infra)
    if not ativos:
        return resultado

    # piso = coluna mais grave entre os gatilhos confirmados
    piso_idx, piso_gatilhos = resultado["indice"], []
    for campo, rotulo in ativos:
        estagio_piso = config.PISO_GATILHOS.get(campo)
        if estagio_piso is None:
            continue
        idx = config.ESTAGIOS.index(estagio_piso)
        if idx > resultado["indice"]:
            piso_gatilhos.append((idx, rotulo, estagio_piso))
            piso_idx = max(piso_idx, idx)

    if piso_idx <= resultado["indice"]:
        # gatilhos ativos, mas nenhum acima do estágio já calculado
        resultado = dict(resultado)
        resultado["justificativas"] = list(resultado["justificativas"]) + [
            "⚙ Gatilhos confirmados em campo: "
            + "; ".join(r for _, r in ativos)]
        return resultado

    estagio_final = config.ESTAGIOS[piso_idx]
    responsaveis = [r for i, r, e in piso_gatilhos if i == piso_idx]
    motivos = list(resultado["justificativas"]) + [
        f"⚑ Estágio elevado de {resultado['estagio']} para {estagio_final} "
        f"pela REGRA DE PISO: gatilho(s) da coluna {estagio_final} do Plano "
        f"confirmado(s) em campo — {'; '.join(responsaveis)}",
    ]
    outros = [r for _, r in ativos if r not in responsaveis]
    if outros:
        motivos.append("⚙ Outros gatilhos confirmados: " + "; ".join(outros))

    detalhes = dict(resultado["detalhes"])
    detalhes["PISO_GATILHOS"] = {"disparou": True,
                                 "motivos": [r for _, r, _ in piso_gatilhos]}
    return _montar_saida(estagio_final, motivos, detalhes)


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
        "# a atualização (célula 4 ou botão do dashboard). O estágio sobe,",
        "# no mínimo, até a coluna do Plano onde o gatilho aparece.",
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

    return IndicadoresNumericos(
        nivel_guaiba_m=guaiba.get("nivel_atual_m"),
        tendencia_guaiba_48h_m=guaiba.get("tendencia_48h_m"),
        dias_guaiba_acima_inundacao=dias_acima,
        afluentes=afluentes,
        acumulado_obs_24h_mm=meteo.get("acumulado_obs_24h_mm", 0.0),
        acumulado_obs_72h_mm=meteo.get("acumulado_obs_72h_mm", 0.0),
        acumulado_obs_7d_mm=meteo.get("acumulado_obs_7d_mm", 0.0),
        previsto_48h_mm=meteo.get("previsto_48h_mm", 0.0),
        dias_chuva_intensa_5d=meteo.get("dias_chuva_intensa_5d", 0),
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
