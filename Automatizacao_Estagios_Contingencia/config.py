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

if IN_COLAB:
    # Pasta do projeto no Google Drive (montado em /content/drive)
    BASE_DIR = Path("/content/drive/MyDrive/Colab Notebooks/Automatizacao_Estagios_Contingencia")
else:
    # Pasta local (VSCode): a própria pasta deste arquivo
    BASE_DIR = Path(__file__).resolve().parent

DADOS_DIR = BASE_DIR / "dados"
DADOS_DIR.mkdir(parents=True, exist_ok=True)

# Pasta de exportação dos arquivos gerados (CSV + Excel) — ponto 3
ARQUIVOS_DIR = BASE_DIR / "arquivos_gerados_2026"
ARQUIVOS_DIR.mkdir(parents=True, exist_ok=True)

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
    "Rio_Cai":                    "87170000",    # afluente
    "Rio_Jacui_TriunfoAmarop":    "85900000",    # afluente principal
}

# ──────────────────────────────────────────────────────────────────────────
# 4. COTAS DE REFERÊNCIA DO GUAÍBA (Cais Mauá) — em METROS
#    Valores oficiais podem ser revisados pela prefeitura/ANA após 2024.
#    AJUSTE AQUI se as referências mudarem.
# ──────────────────────────────────────────────────────────────────────────
COTA_ATENCAO_GUAIBA   = 2.50   # m — "Cota de Atenção"
COTA_ALERTA_GUAIBA    = 3.15   # m — "Cota de Alerta de Inundação"
COTA_INUNDACAO_GUAIBA = 3.60   # m — "Cota de Inundação" (transbordamento)

# Cotas de referência dos afluentes (m). None = sem referência cadastrada,
# nesse caso a lógica usa apenas a TENDÊNCIA de subida.
COTAS_AFLUENTES = {
    "Rio_Gravatai":              {"atencao": 4.00, "alerta": 4.80, "inundacao": 5.50},
    "Rio_dos_Sinos_SaoLeopoldo": {"atencao": 3.50, "alerta": 4.50, "inundacao": 5.00},
    "Rio_Cai":                   {"atencao": 6.00, "alerta": 7.00, "inundacao": 8.00},
    "Rio_Jacui_TriunfoAmarop":   {"atencao": None, "alerta": None, "inundacao": None},
}

# ── Referências p/ os CARDS do dashboard: Nível × Cota de Inundação ──────
# rotulo / municipio / estacao — AJUSTE as cotas de inundação conforme as
# réguas oficiais da Defesa Civil de cada município.
INFO_RIOS_CARDS = [
    {"chave": "Guaiba_PortoAlegre_CaisMaua", "rotulo": "Guaíba",
     "municipio": "Porto Alegre", "estacao": "Cais Mauá (87450004)",
     "cota_inundacao": None},   # None → usa COTA_INUNDACAO_GUAIBA
    {"chave": "Rio_dos_Sinos_SaoLeopoldo", "rotulo": "Rio dos Sinos",
     "municipio": "São Leopoldo", "estacao": "87382000",
     "cota_inundacao": 5.00},
    {"chave": "Rio_Cai", "rotulo": "Rio Caí",
     "municipio": "São Sebastião do Caí", "estacao": "87170000",
     "cota_inundacao": 8.00},
    {"chave": "Rio_Jacui_TriunfoAmarop", "rotulo": "Rio Jacuí",
     "municipio": "Triunfo/Amarópolis", "estacao": "85900000",
     "cota_inundacao": None},   # cota oficial a definir → card mostra "—"
    {"chave": "Rio_Gravatai", "rotulo": "Rio Gravataí",
     "municipio": "Gravataí/Cachoeirinha", "estacao": "87399000",
     "cota_inundacao": 5.50},
]

# ──────────────────────────────────────────────────────────────────────────
# 5. LIMIARES DE CHUVA (mm) — base para os gatilhos dos estágios
#    Calibrados a partir de práticas INMET/Defesa Civil; ajuste livremente.
# ──────────────────────────────────────────────────────────────────────────
LIMIARES_CHUVA = {
    # Previsão (Open-Meteo)
    "previsao_48h_mobilizacao": 50.0,    # mm previstos em 48h → possibilidade de chuvas intensas
    "previsao_48h_alerta":      100.0,   # mm previstos em 48h → padrão de chuva persistente

    # Acumulados observados
    "acumulado_24h_intensa":    60.0,    # mm/24h → chuva intensa
    "acumulado_72h_persistente":120.0,   # mm/72h → chuva intensa persistente
    "acumulado_72h_extrema":    250.0,   # mm/72h → muito acima da média histórica (CRISE)

    # Média histórica mensal aproximada de POA (~110-140 mm/mês).
    # "Muito acima da média" ≈ acumulado do evento > fator x média mensal.
    "media_mensal_historica":   130.0,
    "fator_acima_media_crise":  2.0,
}

# Tendência: subida do nível considerada relevante (m em 48h)
TENDENCIA_SUBIDA_RELEVANTE_M = 0.30

# ──────────────────────────────────────────────────────────────────────────
# 6. FONTES DE SCRAPING
# ──────────────────────────────────────────────────────────────────────────
URL_INMET_ALERTAS = "https://alertas2.inmet.gov.br/"
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
COTA_ATENCAO_RIACHO_IPIRANGA = 1.50
COTA_ALERTA_RIACHO_IPIRANGA  = 2.20

# ── Alertas regionais do Poaclima (marcadores por subprefeitura) ─────────
# Termos que caracterizam risco elevado no campo "Risco:" do popup
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
GATILHOS_TXT = BASE_DIR / "gatilhos_manuais.txt"

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
