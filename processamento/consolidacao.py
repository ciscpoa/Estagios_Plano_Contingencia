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


def _chuva_observada(rios: dict, meteo: dict) -> dict:
    """
    Chuva JÁ OCORRIDA — delega para coleta/chuva_observada.py, que roda a
    cadeia INMET → CEMADEN → ANA → Open-Meteo e só aceita a série que passar
    no controle de qualidade (cobertura + comparação com referência).
    """
    try:
        from coleta import chuva_observada
        return chuva_observada.coletar(rios=rios, meteo=meteo, dias=7)
    except Exception as exc:
        print(f"[CHUVA] coletor falhou por completo ({exc}).")
        return {"ok": False, "fonte": "—", "horaria": pd.DataFrame(),
                "diaria": pd.DataFrame(), "acumulado_24h_mm": None,
                "acumulado_72h_mm": None, "acumulado_7d_mm": None,
                "dias_com_chuva_5d": 0, "dias_chuva_intensa_5d": 0,
                "qualidade": {}, "tentativas": []}


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


    # ── Fallback do nível do Guaíba (ordem importa: MESMO referencial!) ──
    # 1º ANA 87450004 (Cais Mauá) · 2º Poaclima "Cais Mauá C6" (mesma régua,
    # datum de Imbituba) · 3º nivelguaiba.com (último recurso: régua e datum
    # não confirmados — misturar referenciais falseia o % da cota).
    chave_guaiba = "Guaiba_PortoAlegre_CaisMaua"

    # ── Open-Meteo ───────────────────────────────────────────
    try:
        meteo = open_meteo.coletar_previsao()
    except Exception as exc:
        print(f"[Open-Meteo] Falha: {exc}")
        meteo = {"horaria": pd.DataFrame(), "diaria": pd.DataFrame(), "resumo": {}}

    # ── CHUVA OBSERVADA (cadeia auditada de fontes em solo) ──
    chuva_obs = _chuva_observada(rios, meteo)

    # ── Avisos da DEFESA CIVIL DE POA ────────────────────────
    # Fora do bloco do Selenium de propósito: a página é HTML estático e
    # esta é agora a fonte de destaque do painel — ela não pode depender do
    # navegador subir. Se o Selenium cai, o painel perde o mapa do Poaclima,
    # mas continua sabendo se a Defesa Civil publicou aviso.
    avisos_dc = {"vigentes": [], "ultimo": None, "total": 0, "total_ano": 0,
                 "consultado": False, "fonte": "Defesa Civil de Porto Alegre"}
    try:
        from coleta.defesacivil_avisos import coletar_avisos_defesa_civil
        avisos_dc = coletar_avisos_defesa_civil()
    except Exception as exc:
        print(f"[Defesa Civil] Falha: {exc}")

    # ── INMET / Poaclima ─────────────────────────────────────
    inmet = {"alertas": [], "max_severidade": None, "fonte": None}
    previsao_poa = {"ok": False, "dias": [], "previsto_48h_mm": None,
                    "fonte": "Poaclima/Catavento"}
    estacoes_poa = {"ok": False, "estacoes": {}, "acumulado_max_mm": None}
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
        try:
            # previsão oficial que a Defesa Civil de POA exibe (Catavento)
            from coleta.poaclima_scraper import coletar_previsao_poaclima
            previsao_poa = coletar_previsao_poaclima()
        except Exception as exc:
            print(f"[Poaclima-previsão] Falha: {exc}")
        # chuva das estações do Poaclima — usada como referência cruzada
        if True:
            try:
                from coleta.poaclima_scraper import coletar_estacoes_meteo_poaclima
                estacoes_poa = coletar_estacoes_meteo_poaclima()
            except Exception as exc:
                print(f"[Poaclima-estações] Falha: {exc}")

    # ── Fallbacks do Guaíba, na ordem correta de referencial ──
    # A PROCEDÊNCIA viaja junto com o número. Sem isso o card do painel
    # continuava rotulado "Cais Mauá · ANA 87450004" mesmo quando a ANA
    # estava fora e o valor tinha vindo do Poaclima — o painel atribuía à
    # ANA um dado que não era dela, que é exatamente o tipo de fallback
    # silencioso que este projeto decidiu não ter.
    fonte_nivel_guaiba = "Cais Mauá · ANA 87450004"
    if resumo_rios.get(chave_guaiba, {}).get("nivel_atual_m") is None:
        cais_maua_poaclima = (poaclima.get("niveis") or {}).get("cais_maua_m")
        if cais_maua_poaclima is not None:
            print(f"[Fallback] Nível do Guaíba do Poaclima — Cais Mauá C6 "
                  f"({cais_maua_poaclima} m; mesma régua da ANA).")
            fonte_nivel_guaiba = "Cais Mauá C6 · Poaclima (ANA indisponível)"
            resumo_rios[chave_guaiba] = {"nivel_atual_m": cais_maua_poaclima,
                                         "tendencia_48h_m": None,
                                         "ultima_leitura": ts}
        elif usar_selenium:
            # último recurso — datum não confirmado, então avisamos no log
            try:
                from coleta.poaclima_scraper import coletar_nivel_guaiba_fallback
                fb = coletar_nivel_guaiba_fallback()
                if fb.get("nivel_m") is not None:
                    print("[Fallback] ATENÇÃO: usando nivelguaiba.com "
                          f"({fb['nivel_m']} m) — referencial não confirmado; "
                          "o % da cota pode não ser comparável.")
                    fonte_nivel_guaiba = ("nivelguaiba.com · referencial NÃO "
                                          "confirmado")
                    resumo_rios[chave_guaiba] = {"nivel_atual_m": fb["nivel_m"],
                                                 "tendencia_48h_m": None,
                                                 "ultima_leitura": ts}
            except Exception as exc:
                print(f"[Fallback] nivelguaiba.com falhou: {exc}")

    if resumo_rios.get(chave_guaiba, {}).get("nivel_atual_m") is None:
        fonte_nivel_guaiba = "Cais Mauá · ANA 87450004 (sem leitura)"

    return {"timestamp": ts, "rios": rios, "resumo_rios": resumo_rios,
            "fonte_nivel_guaiba": fonte_nivel_guaiba,
            "meteo": meteo, "inmet": inmet, "poaclima": poaclima,
            "avisos_defesa_civil": avisos_dc,
            "chuva_obs": chuva_obs, "previsao_poaclima": previsao_poa,
            "estacoes_meteo_poaclima": estacoes_poa}


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

    co = brutos.get("chuva_obs") or {}
    if co.get("ok"):
        fonte_co = co.get("fonte", "—")
        add("Chuva observada 24h", co.get("acumulado_24h_mm"), "mm", fonte_co)
        add("Chuva observada 72h", co.get("acumulado_72h_mm"), "mm", fonte_co)
        add("Chuva observada 7 dias", co.get("acumulado_7d_mm"), "mm", fonte_co)
        add("Dias com chuva (últimos 5)", co.get("dias_com_chuva_5d"), "dias", fonte_co)
        add("Qualidade da série de chuva", (co.get("qualidade") or {}).get("motivo"),
            "-", fonte_co)
        for t in co.get("tentativas", []):
            add(f"Fonte testada — {t.get('fonte')}",
                f"{t.get('total_7d_mm')} mm/7d · {'ACEITA' if t.get('aprovada') else 'REJEITADA'}"
                f" · {t.get('motivo')}", "-", "controle de qualidade")
    pp = brutos.get("previsao_poaclima") or {}
    if pp.get("ok"):
        add("Chuva prevista 48h (Poaclima/Catavento)",
            pp.get("previsto_48h_mm"), "mm", "Poaclima/Catavento")
        for d in pp.get("dias", [])[:5]:
            add(f"Previsão {d['data']:%d/%m} — {d.get('descricao') or ''}",
                d.get("precipitacao_total_mm"), "mm", "Poaclima/Catavento")

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
    `arquivos_gerados_2026/`:
      • dados_poa_YYYYMMDD_HHMM.csv  — consolidado
      • dados_poa_YYYYMMDD_HHMM.xlsx — Excel com abas: Consolidado,
        Guaiba, Afluentes, Precipitacao_Horaria, Precipitacao_Diaria

    Só roda quando `config.EXPORTAR_ARQUIVOS_RODADA` está ligado — o padrão
    é ligado na máquina local e desligado no GitHub Actions.
    """
    if not getattr(config, "EXPORTAR_ARQUIVOS_RODADA", True):
        print("[EXPORT] Arquivos por rodada desligados nesta execução. "
              "O painel usa dados/ultimo_snapshot.json.")
        return ""

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
