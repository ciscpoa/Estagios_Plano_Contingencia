# -*- coding: utf-8 -*-
"""
consolidacao.py
===============
TAREFA 2 — Consolida todas as fontes (ANA, Open-Meteo, INMET, Poaclima)
em um único DataFrame "wide" de indicadores + séries históricas, e exporta
CSV com data/hora no nome:  dados_poa_YYYYMMDD_HHMM.csv
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

import config
from coleta import ana_api, open_meteo
# Os scrapers Selenium são importados de forma preguiçosa dentro de
# coletar_tudo(), para que o modo --sem-selenium funcione mesmo em
# ambientes sem o Selenium instalado (ex.: Render).


def coletar_tudo(usar_selenium: bool = True) -> dict:
    """
    Executa toda a coleta e retorna um dicionário de "dados brutos":
      {
        "timestamp": datetime,
        "rios": {estacao: DataFrame},
        "resumo_rios": {estacao: {nivel_atual_m, tendencia_48h_m, ...}},
        "meteo": {"horaria": df, "diaria": df, "resumo": {...}},
        "inmet": {...},
        "poaclima": {...},
      }
    """
    ts = datetime.now()
    print(f"=== Coleta iniciada em {ts:%d/%m/%Y %H:%M} ===")

    # ── ANA (rios) ───────────────────────────────────────────
    try:
        rios = ana_api.coletar_niveis_rios(dias=7)
    except Exception as exc:
        print(f"[ANA] Coleta falhou por completo: {exc}")
        rios = {nome: pd.DataFrame(columns=["datahora", "nivel_m", "chuva_mm"])
                for nome in config.ESTACOES_ANA}

    resumo_rios = {nome: ana_api.resumo_estacao(df) for nome, df in rios.items()}

    # Fallback do Guaíba via scraping, se a ANA não trouxe nada
    chave_guaiba = "Guaiba_PortoAlegre_CaisMaua"
    if usar_selenium and resumo_rios.get(chave_guaiba, {}).get("nivel_atual_m") is None:
        try:
            from coleta.poaclima_scraper import coletar_nivel_guaiba_fallback
            fb = coletar_nivel_guaiba_fallback()
        except Exception as exc:
            print(f"[Fallback NivelGuaiba] Falha (seguindo sem): {exc}")
            fb = {"nivel_m": None}
        if fb["nivel_m"] is not None:
            resumo_rios[chave_guaiba] = {
                "nivel_atual_m": fb["nivel_m"],
                "tendencia_48h_m": None,
                "ultima_leitura": ts,
            }

    # ── Open-Meteo ───────────────────────────────────────────
    try:
        meteo = open_meteo.coletar_previsao()
    except Exception as exc:
        print(f"[Open-Meteo] Falha: {exc}")
        meteo = {"horaria": pd.DataFrame(), "diaria": pd.DataFrame(), "resumo": {}}

    # ── INMET / Poaclima ─────────────────────────────────────
    inmet = {"alertas": [], "max_severidade": None, "fonte": None}
    poaclima = {"alerta_vigente": None, "chuva_acumulada_mm": None,
                "niveis": {"usina_gasometro_m": None, "cais_maua_m": None,
                           "riacho_ipiranga_m": None},
                "alertas_regionais": [], "outros_medidores": {}}
    if usar_selenium:
        try:
            from coleta.inmet_scraper import coletar_alertas_inmet
            inmet = coletar_alertas_inmet()
        except Exception as exc:
            print(f"[INMET] Falha: {exc}")
        try:
            from coleta.poaclima_scraper import coletar_poaclima
            poaclima = coletar_poaclima()
        except Exception as exc:
            print(f"[Poaclima] Falha: {exc}")

    # 3ª camada de fallback do Guaíba: medidor Cais Mauá do Poaclima
    cais_maua_poaclima = (poaclima.get("niveis") or {}).get("cais_maua_m")
    if (resumo_rios.get(chave_guaiba, {}).get("nivel_atual_m") is None
            and cais_maua_poaclima is not None):
        print(f"[Fallback] Usando Cais Mauá do Poaclima como nível do Guaíba "
              f"({cais_maua_poaclima} m)")
        resumo_rios[chave_guaiba] = {
            "nivel_atual_m": cais_maua_poaclima,
            "tendencia_48h_m": None,
            "ultima_leitura": ts,
        }

    return {"timestamp": ts, "rios": rios, "resumo_rios": resumo_rios,
            "meteo": meteo, "inmet": inmet, "poaclima": poaclima}


def montar_dataframe(brutos: dict) -> pd.DataFrame:
    """
    Constrói o DataFrame consolidado (formato "longo": indicador | valor | unidade | fonte).
    Esse formato entra direto na DataTable do dashboard e no CSV.
    """
    ts = brutos["timestamp"]
    linhas: list[dict] = []

    def add(indicador, valor, unidade, fonte):
        linhas.append({
            "datahora_extracao": ts.strftime("%d/%m/%Y %H:%M"),
            "indicador": indicador,
            "valor": valor,
            "unidade": unidade,
            "fonte": fonte,
        })

    # Rios (ANA)
    for nome, resumo in brutos["resumo_rios"].items():
        add(f"Nível {nome}", resumo.get("nivel_atual_m"), "m", "ANA / fallback")
        add(f"Tendência 48h {nome}", resumo.get("tendencia_48h_m"), "m/48h", "ANA")

    # Cotas de referência do Guaíba (para leitura no dashboard)
    add("Cota de Atenção (Guaíba)", config.COTA_ATENCAO_GUAIBA, "m", "Plano Contingência")
    add("Cota de Alerta (Guaíba)", config.COTA_ALERTA_GUAIBA, "m", "Plano Contingência")
    add("Cota de Inundação (Guaíba)", config.COTA_INUNDACAO_GUAIBA, "m", "Plano Contingência")

    # Meteo (Open-Meteo)
    for chave, valor in (brutos["meteo"].get("resumo") or {}).items():
        unidade = "dias" if "dias" in chave else "mm"
        add(chave, valor, unidade, "Open-Meteo")

    # INMET
    add("Aviso INMET (máx severidade)", brutos["inmet"].get("max_severidade"), "-", "INMET")
    add("Qtd avisos INMET vigentes", len(brutos["inmet"].get("alertas") or []), "un", "INMET")

    # Poaclima — alerta, chuva e os 3 medidores de nível
    add("Alerta Poaclima vigente", brutos["poaclima"].get("alerta_vigente"), "-", "Poaclima")
    add("Chuva acumulada Poaclima", brutos["poaclima"].get("chuva_acumulada_mm"), "mm", "Poaclima")

    niveis_poa = brutos["poaclima"].get("niveis") or {}
    rotulos_medidores = {
        "usina_gasometro_m": "Nível Usina do Gasômetro (Poaclima)",
        "cais_maua_m":       "Nível Cais Mauá (Poaclima)",
        "riacho_ipiranga_m": "Nível Riacho Ipiranga (Poaclima)",
    }
    for chave, rotulo in rotulos_medidores.items():
        add(rotulo, niveis_poa.get(chave), "m", "Poaclima")

    # Demais estações fluviométricas do mapa (nomes como aparecem no popup)
    for nome_est, nivel in (brutos["poaclima"].get("outros_medidores") or {}).items():
        add(f"Nível {nome_est} (Poaclima)", nivel, "m", "Poaclima")

    # Alertas regionais da Defesa Civil (marcadores por subprefeitura)
    alertas_reg = brutos["poaclima"].get("alertas_regionais") or []
    add("Alertas regionais vigentes (Defesa Civil)", len(alertas_reg), "un", "Poaclima")
    for al in alertas_reg:
        regiao = al.get("regiao_nome") or f"Região {al.get('regiao_num')}"
        add(f"Alerta regional — ({al.get('regiao_num')}) {regiao}",
            f"{al.get('risco')} · {al.get('tipo')} · até {al.get('fim')}",
            "-", "Poaclima/Defesa Civil")

    return pd.DataFrame(linhas)


def exportar_csv(df: pd.DataFrame, brutos: dict) -> str:
    """
    Exporta os dados brutos com o timestamp obrigatório no nome, na pasta
    `arquivos_gerados_2026/` (dentro da pasta de trabalho no Drive):
      • dados_poa_YYYYMMDD_HHMM.csv  — consolidado
      • dados_poa_YYYYMMDD_HHMM.xlsx — Excel com abas: Consolidado,
        Guaiba, Afluentes, Precipitacao_Horaria, Precipitacao_Diaria
    """
    ts = brutos["timestamp"]
    base = config.ARQUIVOS_DIR / f"dados_poa_{ts:%Y%m%d_%H%M}"

    caminho_csv = base.with_suffix(".csv")
    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")
    print(f"[EXPORT] CSV salvo em: {caminho_csv}")

    caminho_xlsx = base.with_suffix(".xlsx")
    try:
        with pd.ExcelWriter(caminho_xlsx, engine="openpyxl") as xls:
            df.to_excel(xls, sheet_name="Consolidado", index=False)

            guaiba = brutos["rios"].get("Guaiba_PortoAlegre_CaisMaua")
            if guaiba is not None and not guaiba.empty:
                guaiba.to_excel(xls, sheet_name="Guaiba", index=False)

            partes = []
            for nome, serie in brutos["rios"].items():
                if nome == "Guaiba_PortoAlegre_CaisMaua" or serie is None or serie.empty:
                    continue
                # coerção numérica evita FutureWarning do concat com colunas all-NA
                p = serie.copy()
                for col in ("nivel_m", "chuva_mm"):
                    if col in p:
                        p[col] = pd.to_numeric(p[col], errors="coerce")
                partes.append(p.assign(rio=nome))
            if partes:
                pd.concat(partes, ignore_index=True).to_excel(
                    xls, sheet_name="Afluentes", index=False)

            horaria = brutos["meteo"].get("horaria")
            if horaria is not None and not horaria.empty:
                horaria.to_excel(xls, sheet_name="Precipitacao_Horaria", index=False)
            diaria = brutos["meteo"].get("diaria")
            if diaria is not None and not diaria.empty:
                diaria.to_excel(xls, sheet_name="Precipitacao_Diaria", index=False)
        print(f"[EXPORT] Excel salvo em: {caminho_xlsx}")
    except Exception as exc:
        print(f"[EXPORT] Falha ao gerar Excel ({exc}); CSV segue disponível.")

    return str(caminho_xlsx if caminho_xlsx.exists() else caminho_csv)


def carregar_ultimo_csv() -> pd.DataFrame | None:
    """Carrega o consolidado mais recente (usado por análises ad-hoc)."""
    arquivos = sorted(config.ARQUIVOS_DIR.glob("dados_poa_*.csv"))
    if not arquivos:
        return None
    return pd.read_csv(arquivos[-1], encoding="utf-8-sig")
