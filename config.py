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

# Exportar ou não os arquivos por rodada (dados_poa_AAAAMMDD_HHMM.csv/.xlsx).
#
# Eles servem para conferência manual na máquina local. No GitHub Actions não
# têm leitor nenhum — o painel lê `dados/ultimo_snapshot.json` — e só somavam
# ~95 KB por execução ao repositório. Então: ligados no local, desligados no
# CI. Para forçar um dos dois, defina a variável de ambiente
# EXPORTAR_ARQUIVOS_RODADA como 1 (liga) ou 0 (desliga).
_no_github_actions = os.environ.get("GITHUB_ACTIONS", "").strip().lower() == "true"
EXPORTAR_ARQUIVOS_RODADA = os.environ.get(
    "EXPORTAR_ARQUIVOS_RODADA", "0" if _no_github_actions else "1"
).strip().lower() in ("1", "true", "sim", "yes", "s")


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
    "Rio_Jacui_Triunfo":          "85900000",    # Jacuí — RIO PARDO (convencional)
    # ═══ Taquari — telemétricas de 15 min, confirmadas na API em 04/08/2026 ═══
    # Códigos conferidos no BOLETIM DO SAH RIO TAQUARI (SGB, 30/07/2026):
    #   86510000 = MUÇUM  ·  86720000 = ENCANTADO  (não o contrário!)
    "Rio_Taquari_Mucum":          "86510000",    # Muçum — SGB/SAH Taquari
    "Rio_Taquari_Encantado":      "86720000",    # Encantado — SGB/SAH Taquari
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
        "faixa_lag_h": (4, 36),
        "provisorio": True,
    },
    "Rio_dos_Sinos_SaoLeopoldo": {
        "rotulo": "Sinos (São Leopoldo)",
        "tempo_viagem_h": 24,
        "faixa_lag_h": (8, 72),
        "provisorio": True,
    },
    "Rio_Cai": {
        "rotulo": "Caí (Barca do Caí)",
        "tempo_viagem_h": 36,
        "faixa_lag_h": (12, 96),
        "provisorio": True,
    },
    "Rio_Jacui_Triunfo": {
        "rotulo": "Jacuí (Rio Pardo)",
        "tempo_viagem_h": 72,
        "faixa_lag_h": (24, 120),
        "provisorio": True,
    },
    # O Taquari desemboca no Jacuí em Triunfo, logo acima do Delta: é o
    # afluente que faltava no painel. Muçum e Encantado ficam a ~150 km do
    # Guaíba — os tempos abaixo são PROVISÓRIOS, como os demais.
    "Rio_Taquari_Mucum": {
        "rotulo": "Taquari (Muçum)",
        "tempo_viagem_h": 60,
        "faixa_lag_h": (24, 120),
        "provisorio": True,
    },
    "Rio_Taquari_Encantado": {
        "rotulo": "Taquari (Encantado)",
        "tempo_viagem_h": 54,
        "faixa_lag_h": (24, 108),
        "provisorio": True,
    },
}

# A previsão usa somente água já observada a montante e deslocada pelo tempo
# de viagem. Vinte e quatro horas preservam uma janela útil sem extrapolar
# além do menor conjunto de sinais disponíveis.
HORIZONTE_PREVISAO_GUAIBA_H = 24
DIAS_HISTORICO_MODELO_GUAIBA = 365
HISTORICO_MODELO_GUAIBA_CSV = DADOS_DIR / "historico_niveis_ana.csv"
MIN_DIAS_HISTORICO_MODELO_GUAIBA = 300
MIN_AMOSTRAS_MODELO_GUAIBA = 1000
MIN_AMOSTRAS_MODELO_RECENTE_GUAIBA = 48
JANELA_ONDA_AFLUENTE_H = 12
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
    # ═══ Jacuí — o código 85900000 é a estação RIO PARDO, NÃO Triunfo ═══
    # (fonte: SGB, relatório da inundação de maio/2024). O próprio SAH Guaíba
    # do SGB usa RIO PARDO como estação de referência do Jacuí nos boletins de
    # 23/07/2026 e 26/07/2026 — ou seja, a estação está certa; o que faltava
    # era a cota da RÉGUA DELA.
    # Cota de inundação em Rio Pardo = 12,50 m (Defesa Civil de Rio Pardo,
    # citada na Gazeta do Sul em 24/07/2026; mesma cota usada pelos painéis
    # que leem a 85900000). Pico histórico: 20,04 m em 05/05/2024.
    # Atenção e alerta ainda NÃO localizadas em fonte oficial → None.
    # CONFIRMAR as três com o SAH Guaíba (alerta.guaiba@sgb.gov.br).
    "Rio_Jacui_Triunfo":  {"atencao": None, "alerta": None, "inundacao": 12.50},
    # ═══ Taquari — SGB/SAH Rio Taquari, boletim de 30/07/2026 ═══
    # (valores lidos nos gráficos do boletim, em cm → m)
    "Rio_Taquari_Mucum":     {"atencao": 5.00, "alerta": 9.00, "inundacao": 18.00},
    "Rio_Taquari_Encantado": {"atencao": 5.00, "alerta": 9.00, "inundacao": 12.00},
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
     "cota_inundacao": 12.50},         # Defesa Civil de Rio Pardo
    {"chave": "Rio_Taquari_Mucum", "rotulo": "Rio Taquari",
     "municipio": "Muçum", "estacao": "ANA 86510000",
     "cota_inundacao": 18.00},         # SGB/SAH Rio Taquari
    {"chave": "Rio_Taquari_Encantado", "rotulo": "Rio Taquari",
     "municipio": "Encantado", "estacao": "ANA 86720000",
     "cota_inundacao": 12.00},         # SGB/SAH Rio Taquari
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
# B825 = PORTO ALEGRE - BELEM NOVO no inventário atual do INMET.
# (A B807, citada em notas técnicas antigas, não existe mais no inventário.)
INMET_ESTACAO_POA = "B825"
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

# Regra de PISO (DESATIVADA): antes, um gatilho confirmado em campo elevava
# o estágio até a coluna do Plano onde o gatilho aparece, MESMO com os blocos
# E/OU daquela coluna abertos. Isso quebrava a leitura do Plano: no item 5.1
# cada coluna é uma conjunção de blocos ligados por E, e o gatilho de campo é
# apenas UMA das alternativas DENTRO de um desses blocos — nunca a coluna
# inteira. Um único gatilho marcado deixava o painel travado em ALERTA com
# céu limpo e rios baixos, e ele só descia quando alguém lembrava de voltar o
# txt para "nao".
#
# Com False, os gatilhos continuam entrando normalmente nas regras (são o
# bloco 3 do ALERTA, os blocos 2/3/4 da EMERGÊNCIA e os 2/3/4/5 da CRISE) —
# só perderam o poder de decidir o estágio sozinhos.
PISO_POR_GATILHO_MANUAL = False

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
    "Rio_Taquari_Mucum":           "Taquari (Muçum)",
    "Rio_Taquari_Encantado":       "Taquari (Encantado)",
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


# ──────────────────────────────────────────────────────────────────────────
# 8. COTAS DE CADA CARD (atenção · alerta · inundação) — FONTE: POACLIMA
#    O card coloria por FAIXA DE PORCENTAGEM da cota de inundação
#    (65% / 85% / 100%), o que não é a régua de ninguém: com 2,54 m no Cais
#    Mauá ele pintava amarelo (85% de 3,00 m) enquanto o gráfico já mostrava
#    o nível ACIMA da cota de alerta (2,50 m). Agora card e gráfico leem as
#    MESMAS cotas do Poaclima.
#
#    É função (e não dicionário) de propósito: as constantes do Riacho
#    Ipiranga só são definidas mais abaixo no arquivo, e função só é
#    avaliada na hora da chamada — assim nada depende da ordem das linhas.
# ──────────────────────────────────────────────────────────────────────────
def cotas_do_card(chave: str) -> dict:
    """Cotas da régua DAQUELE card. Cada régua tem referencial próprio."""
    if chave == "Guaiba_PortoAlegre_CaisMaua":
        return {"atencao": COTA_ATENCAO_GUAIBA,
                "alerta": COTA_ALERTA_GUAIBA,
                "inundacao": COTA_INUNDACAO_GUAIBA}
    if chave == "poaclima_gasometro":
        return {"atencao": COTA_ATENCAO_GASOMETRO,
                "alerta": COTA_ALERTA_GASOMETRO,
                "inundacao": COTA_INUNDACAO_GASOMETRO}
    if chave == "poaclima_riacho_ipiranga":
        return {"atencao": COTA_ATENCAO_RIACHO_IPIRANGA,
                "alerta": COTA_ALERTA_RIACHO_IPIRANGA,
                "inundacao": COTA_INUNDACAO_RIACHO_IPIRANGA}
    base = COTAS_AFLUENTES.get(chave) or {}
    return {"atencao": base.get("atencao"),
            "alerta": base.get("alerta"),
            "inundacao": base.get("inundacao")}


# ──────────────────────────────────────────────────────────────────────────
# 9. FILTRO DE PICOS DA TELEMETRIA (ANA)
#    A estação do Cais Mauá transmite, de vez em quando, leituras isoladas
#    ~1,3 m abaixo das vizinhas (ex.: 2,45 → 1,13 → 2,42 em 15 min). Não é
#    o rio: é falha de sensor/transmissão. No gráfico viram aquelas quedas
#    verticais, e no card viram um nível errado se a falha calhar de ser a
#    última leitura da coleta.
#
#    Método: filtro de Hampel — compara cada ponto com a MEDIANA de uma
#    janela de tempo centrada nele. Mediana e MAD são estatísticas robustas:
#    não se deixam puxar pelo próprio pico. O ponto é descartado (vira vazio,
#    abrindo um buraco na linha) quando se afasta da mediana local mais que
#    `desvio_max_m` E mais que `k_mad` desvios absolutos medianos.
#
#    O segundo critério é o que protege as cheias de verdade: numa subida
#    rápida e contínua (Caí subindo 0,3 m/h) o MAD da janela é grande, o
#    limite acompanha, e nada é descartado. Já num pico isolado o MAD segue
#    minúsculo (as vizinhas concordam entre si) e o ponto cai fora.
#
#    ONDE se aplica: só nas estações listadas em "estacoes". O filtro parte
#    do princípio de que a leitura boa é a MAIORIA da janela — verdadeiro no
#    Cais Mauá, que transmite de 15 em 15 min e falha em pontos isolados.
#    NÃO vale para a 85900000 (Rio Pardo/"Jacuí"), que alterna entre duas
#    escalas (~0,38 m e ~9,8 m) por horas seguidas: ali a leitura boa fica em
#    minoria e o filtro apagaria justamente a certa. Aquela estação precisa de
#    outro tratamento (identificar o sensor correto na resposta da ANA), não
#    deste. Lista vazia (ou None) = aplica em todas.
# ──────────────────────────────────────────────────────────────────────────
FILTRO_PICOS_ANA = {
    "ativo": True,
    "estacoes": ["Guaiba_PortoAlegre_CaisMaua"],
    "janela_h": 6,          # janela centrada da mediana móvel
    "desvio_max_m": 0.30,   # piso: variação real menor que isso nunca é pico
    "k_mad": 6.0,           # múltiplo do MAD local (robustez em cheia)
    "min_pontos": 8,        # série curta demais → não filtra
    "avisar": True,         # imprime no log quantos pontos saíram
}


# ──────────────────────────────────────────────────────────────────────────
# 10. PERFIL DE CADA ESTAÇÃO DA ANA (cadência, frescor e faixa plausível)
#
#    Nem toda estação do HidroWebService é telemétrica de verdade. Conferido
#    em 04/08/2026, direto na API (30 dias, estação 85900000):
#
#      · Cota_Sensor e Cota_Display vêm SEMPRE vazias;
#      · Cota_Adotada é idêntica a Cota_Manual em 100% dos registros;
#      · há 2 leituras por dia — 07:00 e 17:00 (intervalos de 10 h e 14 h);
#      · Data_Atualizacao 30/07 14:20 para a medição de 29/07 17:00, ou seja,
#        ~21 h de atraso entre medir e publicar.
#
#    Isto é uma estação CONVENCIONAL (observador lê a régua duas vezes por
#    dia), não telemétrica. O card do "Jacuí" mostrava 10,89 m sem dizer que
#    o número tinha 30 h de idade. Daí `idade_max_h`: acima disso o painel
#    marca a leitura como antiga em vez de exibi-la como se fosse de agora.
#
#    `faixa_m` é a faixa fisicamente possível NA RÉGUA DAQUELA ESTAÇÃO (cada
#    uma tem seu referencial). Serve contra a publicação transitória de lixo:
#    em 29–30/07 a ANA publicou, de 15 em 15 min, leituras de 0,00–0,40 m na
#    85900000 enquanto o rio estava em 9,8 m; depois ela mesma corrigiu a
#    série (por isso a consulta de hoje não traz mais esses valores). O filtro
#    de Hampel não pega esse caso — o lixo era MAIORIA. A faixa pega.
#    Leitura fora da faixa vira vazio (buraco honesto), não some da série.
#
#    Os limites abaixo são folgados de propósito. Se algum dia uma cheia real
#    passar do teto, é o teto que está errado — corrija aqui.
# ──────────────────────────────────────────────────────────────────────────
PERFIL_ESTACOES_ANA = {
    "Guaiba_PortoAlegre_CaisMaua": {
        "faixa_m": (-0.50, 8.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_Gravatai": {
        "faixa_m": (0.00, 12.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_dos_Sinos_SaoLeopoldo": {
        "faixa_m": (0.00, 15.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_Cai": {
        "faixa_m": (0.00, 20.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_Cai_Montenegro": {
        "faixa_m": (0.00, 15.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_Cai_NovaPalmira": {
        "faixa_m": (0.00, 12.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    # Piso 1,50 m: em 371 dias de série a leitura de régua nunca ficou abaixo
    # de 2,00 m, e o lixo do sensor se concentra entre 0,00 e 0,40 m.
    # CONFERIR o mínimo histórico com o SGB antes de tratar como definitivo.
    "Rio_Jacui_Triunfo": {
        "faixa_m": (1.50, 25.00), "idade_max_h": 30, "cadencia": "convencional",
        "nota": "leitura de régua às 07h e 17h, publicada com ~1 dia de atraso"},
    # Taquari: 15 min de cadência e ~3 h de idade na conferência de 04/08/2026.
    # Tetos acima da maior cheia registrada em cada régua (26,11 m em Muçum e
    # 23,14 m em Encantado, ambas em 2023/2024, segundo o boletim do SGB).
    "Rio_Taquari_Mucum": {
        "faixa_m": (0.00, 30.00), "idade_max_h": 6, "cadencia": "telemétrica"},
    "Rio_Taquari_Encantado": {
        "faixa_m": (0.00, 28.00), "idade_max_h": 6, "cadencia": "telemétrica"},
}


def perfil_estacao(nome_ou_codigo) -> dict:
    """Perfil da estação a partir do nome amigável OU do código da ANA."""
    chave = str(nome_ou_codigo)
    if chave in PERFIL_ESTACOES_ANA:
        return PERFIL_ESTACOES_ANA[chave]
    for nome, codigo in ESTACOES_ANA.items():
        if str(codigo) == chave:
            return PERFIL_ESTACOES_ANA.get(nome, {})
    return {}
