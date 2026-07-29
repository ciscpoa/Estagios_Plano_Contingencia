# -*- coding: utf-8 -*-
"""
config.py
=========
Configuração central do projeto de monitoramento dos Estágios Operacionais
do Plano de Contingência de Porto Alegre/RS.

Todos os caminhos, códigos de estação, cotas de referência e limiares de
chuva ficam AQUI, para facilitar ajuste sem tocar no restante do código.
"""

import os
import sys
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────
# 1. DETECÇÃO DE AMBIENTE (VSCode local  vs  Google Colab)
# ──────────────────────────────────────────────────────────────────────────
IN_COLAB = "google.colab" in sys.modules
# O Render define a variável RENDER=true automaticamente em todo serviço
IN_RENDER = os.environ.get("RENDER", "").lower() in ("1", "true", "yes")

if IN_COLAB:
    # Pasta do projeto no Google Drive (montado em /content/drive)
    BASE_DIR = Path("/content/drive/MyDrive/Colab Notebooks/Automatizacao_Estagios_Contingencia")
else:
    # Pasta local (VSCode) ou container (Render/Docker): a pasta deste arquivo
    BASE_DIR = Path(__file__).resolve().parent

# Onde gravar dados/arquivos. No Render, se um disco persistente for
# montado (ex.: /var/data), basta definir DIRETORIO_DADOS=/var/data.
# Sem disco, tudo fica no container (efêmero) — o agendador recria a
# cada boot, então o painel continua funcionando normalmente.
_SAIDA = Path(os.environ.get("DIRETORIO_DADOS", BASE_DIR))

DADOS_DIR = _SAIDA / "dados"
DADOS_DIR.mkdir(parents=True, exist_ok=True)

# Pasta de exportação dos arquivos gerados (CSV + Excel)
ARQUIVOS_DIR = _SAIDA / "arquivos_gerados_2026"
ARQUIVOS_DIR.mkdir(parents=True, exist_ok=True)


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, padrao))
    except (TypeError, ValueError):
        return padrao


def _env_bool(nome: str, padrao: bool) -> bool:
    v = os.environ.get(nome)
    if v is None:
        return padrao
    return v.strip().lower() in ("1", "true", "yes", "sim", "ok")


# ── Operação em servidor (Render) ────────────────────────────────────────
# Agendador embutido: recoleta os dados de tempos em tempos dentro do
# próprio web service (não exige Cron Job pago).
AGENDADOR_ATIVO = _env_bool("AGENDADOR", IN_RENDER)
INTERVALO_COLETA_MIN = _env_int("INTERVALO_COLETA_MIN", 30)
USAR_SELENIUM = _env_bool("USAR_SELENIUM", True)

# Arquivo local com as credenciais da API da ANA (NÃO versionar no git!)
ANA_CREDENCIAIS_TXT = BASE_DIR / "ANA_API_ID_SENHA.txt"

# ──────────────────────────────────────────────────────────────────────────
# 2. LOCALIZAÇÃO — Porto Alegre / RS
# ──────────────────────────────────────────────────────────────────────────
POA_LAT = -30.0331
POA_LON = -51.2300
TIMEZONE = "America/Sao_Paulo"

# ──────────────────────────────────────────────────────────────────────────
# 3. ANA — HidroWebService (estações telemétricas)
#    Portal: https://www.ana.gov.br/hidrowebservice
# ──────────────────────────────────────────────────────────────────────────
ANA_BASE_URL = "https://www.ana.gov.br/hidrowebservice"

# Códigos de estação telemétrica (ajuste/adicione conforme necessidade).
# Consulte o inventário em https://www.snirh.gov.br/hidroweb/
ESTACOES_ANA = {
    # nome_amigavel: codigo_estacao
    "Guaiba_PortoAlegre_CaisMaua": "87450004",   # Guaíba - Cais Mauá (POA)
    "Rio_Gravatai":               "87399000",    # afluente
    "Rio_dos_Sinos_SaoLeopoldo":  "87382000",    # afluente
    "Rio_Cai":                    "87170000",    # Barca do Caí (SACE)
    "Rio_Cai_Montenegro":         "87270000",    # Passo Montenegro (SACE)
    "Rio_Cai_NovaPalmira":        "87160000",    # Nova Palmira (SACE)
    "Rio_Jacui_Triunfo":          "85900000",    # Jacuí — CONFIRMAR código c/ SGB
}

# Afluentes usados para relacionar as ondas de cheia ao nível do Guaíba.
# `tempo_viagem_h` desloca a leitura da estação até o instante estimado de
# chegada ao Guaíba. Os valores abaixo são OPERACIONAIS/PROVISÓRIOS: devem ser
# recalibrados com séries históricas e medições de velocidade/vazão.
#
# A estação 85900000 fica em Rio Pardo (não em Triunfo); por isso o tempo do
# Jacuí é especialmente incerto e sua identificação permanece explícita.
AFLUENTES_GUAIBA = {
    "Rio_Gravatai": {
        "rotulo": "Gravataí",
        "tempo_viagem_h": 12,
        "provisorio": True,
    },
    "Rio_dos_Sinos_SaoLeopoldo": {
        "rotulo": "Sinos (São Leopoldo)",
        "tempo_viagem_h": 24,
        "provisorio": True,
    },
    "Rio_Cai": {
        "rotulo": "Caí (Barca do Caí)",
        "tempo_viagem_h": 36,
        "provisorio": True,
    },
    "Rio_Jacui_Triunfo": {
        "rotulo": "Jacuí (Rio Pardo)",
        "tempo_viagem_h": 72,
        "provisorio": True,
    },
}

# A previsão usa somente água já observada a montante e deslocada pelo tempo
# de viagem. Vinte e quatro horas preservam uma janela útil sem extrapolar
# além do menor conjunto de sinais disponíveis.
HORIZONTE_PREVISAO_GUAIBA_H = 24
MIN_AMOSTRAS_MODELO_GUAIBA = 48
INTERPOLACAO_MAX_GAP_H = 6
RIDGE_ALPHA_GUAIBA = 1.0

# ──────────────────────────────────────────────────────────────────────────
# 4. COTAS DE REFERÊNCIA DO GUAÍBA (Cais Mauá) — em METROS
#    Valores oficiais podem ser revisados pela prefeitura/ANA após 2024.
#    AJUSTE AQUI se as referências mudarem.
# ──────────────────────────────────────────────────────────────────────────
# ── COTAS DO GUAÍBA — atenção ao REFERENCIAL (datum) de cada régua! ──────
# FONTE: painel Poaclima da Prefeitura de Porto Alegre (Monitoramento
# Hidrometeorológico da Defesa Civil de POA), réguas conferidas em
# 26/07/2026 — responsáveis técnicos SEMA-RS (Cais Mauá) e ANA (Gasômetro).
#
# O nível que o pipeline usa na classificação vem da estação da ANA
# 87450004 (CAIS MAUÁ), cujo zero é referenciado ao marégrafo de Imbituba.
# Portanto as constantes abaixo são as do Cais Mauá.
COTA_ATENCAO_GUAIBA   = 2.05   # m
COTA_ALERTA_GUAIBA    = 2.50   # m
COTA_INUNDACAO_GUAIBA = 3.00   # m

# A régua da USINA DO GASÔMETRO tem referência de nível PRÓPRIA — as
# leituras não são comparáveis com as do Cais Mauá (por isso os valores
# diferem no mesmo instante). Cotas do painel Poaclima/Defesa Civil POA:
# (obs.: a nota da SEMA de 28/05/2024 citava 3,15/3,60 para a estação
#  emergencial instalada naquele mês; o painel operacional atual usa os
#  valores abaixo, que são os vigentes.)
COTA_ATENCAO_GASOMETRO   = 1.70
COTA_ALERTA_GASOMETRO    = 2.10
COTA_INUNDACAO_GASOMETRO = 2.60

# Cotas de referência dos afluentes (m). None = sem referência cadastrada,
# nesse caso a lógica usa apenas a TENDÊNCIA de subida.
COTAS_AFLUENTES = {
    # ═══ VERIFICADAS — SGB/CPRM, Boletim do SAH Rio Caí ═══
    "Rio_Cai":            {"atencao": 5.00, "alerta": 7.00, "inundacao": 10.50},
    "Rio_Cai_Montenegro": {"atencao": 3.00, "alerta": 4.00, "inundacao": 6.00},
    "Rio_Cai_NovaPalmira":{"atencao": 2.00, "alerta": 3.00, "inundacao": 4.70},
    # ═══ Sinos — Plano de Contingência de São Leopoldo / Defesa Civil ═══
    # (inundação 4,50 m confirmada; 4,30 m = risco de transbordamento)
    "Rio_dos_Sinos_SaoLeopoldo": {"atencao": 3.50, "alerta": 4.30, "inundacao": 4.50},
    # ═══ Gravataí (Passo das Canoas) — ANA/estação, via Defesa Civil ═══
    # Cota de ATENÇÃO não localizada em fonte oficial → None (não inventar).
    "Rio_Gravatai":       {"atencao": None, "alerta": 4.25, "inundacao": 4.75},
    # ═══ Jacuí — ATENÇÃO: o código 85900000 é a estação RIO PARDO, ═══
    # NÃO Triunfo (fonte: SGB, relatório da inundação de maio/2024).
    # A cota de inundação do Jacuí em TRIUNFO é 4,67 m (Defesa Civil de
    # Triunfo), mas o código ANA de Triunfo ainda precisa ser confirmado no
    # HidroWeb/SNIRH. Enquanto isso, sem cota para a estação lida.
    "Rio_Jacui_Triunfo":  {"atencao": None, "alerta": None, "inundacao": None},
}

# ── Referências p/ os CARDS do dashboard: Nível × Cota de Inundação ──────
# rotulo / municipio / estacao — AJUSTE as cotas de inundação conforme as
# réguas oficiais da Defesa Civil de cada município.
INFO_RIOS_CARDS = [
    # Cada card usa a cota da SUA régua (os referenciais são diferentes!).
    # Cards sem cota oficial mostram "cota de inundação: não informada".
    {"chave": "Guaiba_PortoAlegre_CaisMaua", "rotulo": "Guaíba",
     "municipio": "Porto Alegre", "estacao": "Cais Mauá · ANA 87450004",
     "cota_inundacao": 3.00},          # Poaclima/SEMA-RS (datum Imbituba)
    {"chave": "poaclima_gasometro", "rotulo": "Guaíba",
     "municipio": "Porto Alegre", "estacao": "Usina do Gasômetro · Poaclima",
     "cota_inundacao": 2.60},          # Poaclima/DC-POA (datum local próprio)
    {"chave": "poaclima_riacho_ipiranga", "rotulo": "Riacho Ipiranga",
     "municipio": "Porto Alegre", "estacao": "Arroio Dilúvio · Poaclima",
     "cota_inundacao": 4.00},          # Poaclima/DC-POA (alerta 3,00)
    {"chave": "Rio_dos_Sinos_SaoLeopoldo", "rotulo": "Rio dos Sinos",
     "municipio": "São Leopoldo", "estacao": "ANA 87382000",
     "cota_inundacao": 4.50},          # Defesa Civil de São Leopoldo
    {"chave": "Rio_Cai", "rotulo": "Rio Caí",
     "municipio": "São Sebastião do Caí", "estacao": "Barca do Caí · 87170000",
     "cota_inundacao": 10.50},         # SGB/CPRM — SAH Rio Caí
    {"chave": "Rio_Cai_Montenegro", "rotulo": "Rio Caí",
     "municipio": "Montenegro", "estacao": "Passo Montenegro · 87270000",
     "cota_inundacao": 6.00},          # SGB/CPRM — SAH Rio Caí
    {"chave": "Rio_Cai_NovaPalmira", "rotulo": "Rio Caí",
     "municipio": "Caxias do Sul", "estacao": "Nova Palmira · 87160000",
     "cota_inundacao": 4.70},          # SGB/CPRM — SAH Rio Caí
    {"chave": "Rio_Jacui_Triunfo", "rotulo": "Rio Jacuí",
     "municipio": "Rio Pardo", "estacao": "ANA 85900000",
     "cota_inundacao": None},          # 85900000 = Rio Pardo (não Triunfo)
    {"chave": "Rio_Gravatai", "rotulo": "Rio Gravataí",
     "municipio": "Gravataí", "estacao": "Passo das Canoas · ANA 87399000",
     "cota_inundacao": 4.75},          # ANA/Defesa Civil (alerta 4,25 m)
]

# ──────────────────────────────────────────────────────────────────────────
# 5. LIMIARES DE CHUVA (mm) — base para os gatilhos dos estágios
#    Calibrados a partir de práticas INMET/Defesa Civil; ajuste livremente.
# ──────────────────────────────────────────────────────────────────────────
# Referência: escala oficial de AVISOS DE CHUVAS INTENSAS do INMET —
#   Amarelo (perigo potencial): 20-30 mm/h  ou  30-50 mm/dia
#   Laranja (perigo)          : 30-60 mm/h  ou  50-100 mm/dia
#   Vermelho (grande perigo)  : > 60 mm/h   ou  > 100 mm/dia
# Os limiares antigos (60 mm/24h para "intensa") ficavam ACIMA do laranja do
# INMET: só disparavam em evento excepcional, e por isso o bloco de chuva do
# ALERTA nunca fechava numa semana de chuva forte porém não recordista.
LIMIARES_CHUVA = {
    # ── Chuva JÁ OCORRIDA ────────────────────────────────────
    "dia_com_chuva_relevante":   5.0,    # mm/dia → conta como "dia de chuva"
    "acumulado_24h_moderada":   30.0,    # mm/24h → piso do amarelo INMET
    "acumulado_24h_intensa":    50.0,    # mm/24h → piso do laranja INMET
    "acumulado_72h_moderado":   50.0,    # mm/72h → chuva relevante acumulada
    "acumulado_72h_persistente":80.0,    # mm/72h → chove há dias
    "acumulado_72h_extrema":    200.0,   # mm/72h → muito acima da média (CRISE)

    # ── Chuva PREVISTA ───────────────────────────────────────
    "previsao_48h_mobilizacao": 25.0,    # mm/48h → previsão de chuvas mais intensas
    "previsao_48h_alerta":      50.0,    # mm/48h → previsão forte
    "previsao_5d_continuidade": 40.0,    # mm/5d  → o padrão de chuva continua
    "previsao_5d_alerta":       80.0,    # mm/5d  → continuidade forte
    "dias_previsao_continuidade": 2,     # nº de dias com chuva previstos

    # Média histórica mensal aproximada de POA (~110-140 mm/mês).
    "media_mensal_historica":   130.0,
    "fator_acima_media_crise":  2.0,
}

# ── Controle de qualidade da chuva OBSERVADA ─────────────────────────────
# Uma série de pluviômetro só vira a chuva oficial do painel se passar aqui.
# Foi o que faltava quando o painel exibiu ~2 mm/dia numa semana de chuva
# forte: a estação fluviométrica do Cais Mauá transmitia de forma esparsa.
QUALIDADE_CHUVA = {
    # Exigência PREFERENCIAL: uma estação que transmite de hora em hora deve
    # entregar quase todas as horas da janela. 80% deixa margem só para
    # manutenção e falhas curtas de transmissão.
    # 75%: régua definida com o CISC. Abaixo disso a estação do INMET é
    # descartada e a chuva volta para o pluviômetro da ANA em Gravataí.
    "cobertura_minima_pct":         75.0,
    # Rede de segurança: se NENHUMA fonte em solo alcançar os 80%, o coletor
    # roda uma 2ª passada com este piso antes de cair no modelo global.
    # Um pluviômetro com 60% de cobertura ainda é melhor que o Open-Meteo.
    "cobertura_minima_absoluta_pct": 45.0,
    "referencia_minima_mm":         15.0,  # abaixo disso não dá p/ comparar
    "razao_minima_vs_referencia":   0.45,  # < 45% da referência → subestimando
    "razao_maxima_vs_referencia":   3.00,  # > 300% → série acumulada/duplicada
}

# Ordem de preferência dos pluviômetros da ANA. O Cais Mauá é estação
# FLUVIOMÉTRICA (existe para medir nível) — vai para o fim da fila.
ANA_ORDEM_PLUVIOMETROS = [
    "Rio_Gravatai", "Rio_dos_Sinos_SaoLeopoldo", "Rio_Cai_Montenegro",
    "Rio_Cai", "Rio_Cai_NovaPalmira", "Guaiba_PortoAlegre_CaisMaua",
]

# ── CEMADEN — pluviômetros automáticos da rede federal ───────────────────
# Endpoint do Mapa Interativo (não é API documentada: confira se parar).
CEMADEN_ATIVO = _env_bool("CEMADEN_ATIVO", True)
CEMADEN_URL_JSON = os.environ.get(
    "CEMADEN_URL_JSON",
    "https://sjc.salvar.cemaden.gov.br/resources/graficos/interativo/getJson2.php?uf=RS")

# Tendência: subida do nível considerada relevante (m em 48h)
TENDENCIA_SUBIDA_RELEVANTE_M = 0.30

# ──────────────────────────────────────────────────────────────────────────
# 6. FONTES DE SCRAPING
# ──────────────────────────────────────────────────────────────────────────
# o alertas2 saiu do ar / foi substituído pelo avisos.inmet.gov.br
URL_INMET_ALERTAS = "https://avisos.inmet.gov.br/"
URL_INMET_MAPAS   = "https://portal.inmet.gov.br/"
URL_POACLIMA      = "https://prefeitura.poa.br/poaclima/"
# (endereço antigo poaclima.prefeitura.poa.br foi DESATIVADO — DNS não resolve)
# Nível do Guaíba divulgado pelo DMAE/Prefeitura (fallback do scraping)
URL_NIVEL_GUAIBA_PMPA = "https://nivelguaiba.com/"   # espelho público do nível

# Medidores de nível exibidos no Poaclima → rótulos como aparecem na página
# (usados pelo scraper para ancorar a busca do valor "N,NN m")
MEDIDORES_POACLIMA = {
    "usina_gasometro_m": ("usina do gasômetro", "gasômetro", "gasometro"),
    "cais_maua_m":       ("cais mauá", "cais maua"),
    "riacho_ipiranga_m": ("riacho ipiranga", "arroio dilúvio", "ipiranga"),
}

# Cotas de referência do Riacho Ipiranga/Arroio Dilúvio (m) — AJUSTE conforme
# a régua oficial; usadas no gatilho "córregos da cidade começam a subir"
# do estágio de ALERTA. None desativa o gatilho por cota (fica só tendência).
# Riacho Ipiranga / Arroio Dilúvio — cotas do painel Poaclima (Defesa Civil
# de POA; responsável técnico ANA), conferidas em 26/07/2026.
COTA_ATENCAO_RIACHO_IPIRANGA   = 2.55
COTA_ALERTA_RIACHO_IPIRANGA    = 3.00
COTA_INUNDACAO_RIACHO_IPIRANGA = 4.00

# ── Alertas regionais do Poaclima (marcadores por subprefeitura) ─────────
# Termos que caracterizam risco elevado no campo "Risco:" do popup
# ── Chuva observada: estação automática do INMET em Porto Alegre ────────
# A801 = Porto Alegre (Jardim Botânico). Fonte preferencial para a chuva
# JÁ OCORRIDA (pluviômetro na cidade), no lugar do modelo global.
# Estação automática do INMET usada como pluviômetro de referência.
# B807 = PORTO ALEGRE - BELEM NOVO (aeroclube, zona sul), em terreno
# descampado conforme norma da OMM. A A801 (Jardim Botânico) fica como
# vizinha na auto-descoberta, caso a B807 saia do ar.
INMET_ESTACAO_POA = "B807"
# Casar também pelo NOME: se o INMET trocar o código da estação, o painel
# continua achando o Belém Novo sem precisar de edição aqui.
INMET_ESTACAO_POA_NOME = "belem novo"

# Prioridade das fontes de chuva (a 1ª disponível vence):
#   observada → INMET estação → Open-Meteo
#   prevista  → Poaclima/Catavento (mesma da Defesa Civil) → Open-Meteo
PREFERIR_INMET_OBSERVADO = True
PREFERIR_POACLIMA_PREVISAO = True

RISCOS_ELEVADOS_POACLIMA = ("risco alto", "risco muito alto", "risco extremo")
# Nº de regiões simultâneas com risco elevado de Inundação que serve de
# evidência (proxy) de "inundações graves" no estágio de EMERGÊNCIA
N_REGIOES_INUNDACAO_EMERGENCIA = 3

# As 17 regiões do mapa do Poaclima seguem a numeração das Regiões do
# Orçamento Participativo de Porto Alegre (conferido: 15=Sul, 13=Extremo-Sul,
# 17=Ilhas, 16=Centro, 8=Restinga, 4=Lomba do Pinheiro...). AJUSTE se preciso.
REGIOES_POACLIMA = {
    1: "Humaitá/Navegantes", 2: "Noroeste", 3: "Leste",
    4: "Lomba do Pinheiro", 5: "Norte", 6: "Nordeste",
    7: "Partenon", 8: "Restinga", 9: "Glória",
    10: "Cruzeiro", 11: "Cristal", 12: "Centro-Sul",
    13: "Extremo-Sul", 14: "Eixo Baltazar", 15: "Sul",
    16: "Centro", 17: "Ilhas",
}

# ── Gatilhos manuais via ARQUIVO TXT (operação pela Defesa Civil/SMS) ────
# O pipeline lê `gatilhos_manuais.txt` na pasta do projeto: marque "ok"
# no gatilho confirmado em campo e o estágio muda na próxima atualização.
GATILHOS_TXT = Path(os.environ.get(
    "GATILHOS_TXT", BASE_DIR / "gatilhos_manuais.txt"))

# Regra de PISO: gatilho confirmado eleva o estágio, no mínimo, até a
# coluna do Plano (item 5.1) onde o gatilho aparece. Desative com False
# para voltar ao modo estritamente E/OU.
PISO_POR_GATILHO_MANUAL = True

ROTULOS_GATILHOS = {
    # coluna ALERTA
    "familias_deixando_casas":        "Famílias deixando suas casas",
    "aumento_demanda_abrigo":         "Aumento na demanda por abrigo",
    "abrigos_temporarios_instalados": "Abrigos temporários instalados",
    "bloqueio_vias_principais":       "Bloqueio de vias principais",
    "aumento_demanda_saude_clima":    "Aumento de demanda na saúde (evento climático)",
    # coluna SITUAÇÃO DE EMERGÊNCIA
    "inundacoes_graves_ou_deslizamentos":     "Inundações graves e/ou deslizamentos",
    "vias_ou_pontes_danificadas":             "Vias/pontes danificadas ou bloqueadas",
    "interrupcao_parcial_servicos_essenciais":"Interrupção parcial de serviços essenciais",
    "aumento_significativo_desabrigados":     "Aumento significativo de desabrigados",
    "obitos_pelo_evento":                     "Óbito(s) em decorrência do evento",
    "servicos_saude_interrompidos":           "Serviços de saúde interrompidos",
    "risco_alto_desabastecimento":            "Risco alto de desabastecimento",
    # coluna CRISE
    "colapso_drenagem_urbana":                "Colapso da drenagem urbana",
    "interrupcao_infraestrutura_grande_escala":"Interrupção de infraestrutura em grande escala",
    "isolamento_areas_comunidades":           "Isolamento de áreas/comunidades",
    "descontrole_rede_abrigos":               "Descontrole da rede de abrigos",
    "sobrecarga_sistema_saude":               "Sobrecarga do sistema de saúde",
    "necessidade_apoio_federal_estadual":     "Necessidade de apoio estadual/federal",
}

# Piso de estágio por gatilho = coluna do Plano onde o gatilho está escrito
PISO_GATILHOS = {
    **{g: "ALERTA" for g in (
        "familias_deixando_casas", "aumento_demanda_abrigo",
        "abrigos_temporarios_instalados", "bloqueio_vias_principais",
        "aumento_demanda_saude_clima")},
    **{g: "SITUAÇÃO DE EMERGÊNCIA" for g in (
        "inundacoes_graves_ou_deslizamentos", "vias_ou_pontes_danificadas",
        "interrupcao_parcial_servicos_essenciais",
        "aumento_significativo_desabrigados", "obitos_pelo_evento",
        "servicos_saude_interrompidos", "risco_alto_desabastecimento")},
    **{g: "CRISE" for g in (
        "colapso_drenagem_urbana", "interrupcao_infraestrutura_grande_escala",
        "isolamento_areas_comunidades", "descontrole_rede_abrigos",
        "sobrecarga_sistema_saude", "necessidade_apoio_federal_estadual")},
}

# Nomes de exibição das estações (usados nas justificativas e gráficos)
NOMES_EXIBICAO = {
    "Guaiba_PortoAlegre_CaisMaua": "Guaíba (Cais Mauá)",
    "Rio_Gravatai":                "Gravataí (Passo das Canoas)",
    "Rio_dos_Sinos_SaoLeopoldo":   "Sinos (São Leopoldo)",
    "Rio_Cai":                     "Caí (Barca do Caí)",
    "Rio_Cai_Montenegro":          "Caí (Montenegro)",
    "Rio_Cai_NovaPalmira":         "Caí (Nova Palmira)",
    "Rio_Jacui_Triunfo":           "Jacuí (Rio Pardo)",
    "Rio_Jacui_TriunfoAmarop":     "Jacuí (Rio Pardo)",
}

# Cores dos avisos do INMET (padrão oficial de severidade)
CORES_AVISO_INMET = {
    "Amarelo":  "#E3B505",   # Perigo potencial
    "Laranja":  "#F2830B",   # Perigo
    "Vermelho": "#CE1B22",   # Grande perigo
}

# Cores da legenda oficial do Poaclima (risco por região)
CORES_RISCO_POACLIMA = {
    "sem risco":  "#2E9E44",   # verde
    "atenção":    "#E3B505",   # amarelo (Aviso de atenção)
    "alto":       "#F2830B",   # laranja (Alerta de risco alto)
    "muito alto": "#CE1B22",   # vermelho
    "extremo":    "#C2187E",   # magenta
    "sem dado":   "#4A5561",   # cinza
}

# Selenium
SELENIUM_TIMEOUT_S = 25
# teto p/ carregar uma página (o alertas2.inmet travou 2×120s em 26/07)
SELENIUM_PAGELOAD_TIMEOUT_S = 45
SELENIUM_HEADLESS = True

# ──────────────────────────────────────────────────────────────────────────
# 7. NOMES / CORES DOS ESTÁGIOS OPERACIONAIS (item 5.1 do Plano)
# ──────────────────────────────────────────────────────────────────────────
ESTAGIOS = ["NORMALIDADE", "MOBILIZAÇÃO", "ALERTA", "SITUAÇÃO DE EMERGÊNCIA", "CRISE"]

CORES_ESTAGIOS = {
    "NORMALIDADE":            "#2E9E44",  # verde
    "MOBILIZAÇÃO":            "#E3B505",  # amarelo
    "ALERTA":                 "#F2830B",  # laranja
    "SITUAÇÃO DE EMERGÊNCIA": "#CE1B22",  # vermelho
    "CRISE":                  "#6B3FA0",  # roxo
}
