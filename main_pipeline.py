# -*- coding: utf-8 -*-
"""
main_pipeline.py
================
Orquestrador: COLETA → CONSOLIDA → EXPORTA CSV → CLASSIFICA ESTÁGIO.

Uso (VSCode/terminal):
    python main_pipeline.py                # coleta completa (com Selenium)
    python main_pipeline.py --sem-selenium # só APIs (ANA + Open-Meteo)

No Colab, basta importar e chamar `executar_pipeline()`.

Ao final grava `dados/ultimo_snapshot.json` — é esse arquivo que o
dashboard (app.py) lê para renderizar sem precisar recoletar tudo.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

import pandas as pd

import config
from coleta import ana_api
from processamento import alinhamento_afluentes, consolidacao
from logica import estagios


def executar_pipeline(usar_selenium: bool = True,
                      infra: "estagios.InputsInfraestrutura | None" = None) -> dict:
    """Executa o fluxo completo e retorna o snapshot final."""
    # 0) Gatilhos manuais: se não vierem por parâmetro, lê do TXT
    #    (gatilhos_manuais.txt — Defesa Civil marca "ok" no confirmado)
    if infra is None:
        infra = estagios.ler_gatilhos_txt()

    # 1) Coleta
    brutos = consolidacao.coletar_tudo(usar_selenium=usar_selenium)

    # 2) Consolidação + export CSV com timestamp
    df = consolidacao.montar_dataframe(brutos)
    caminho_csv = consolidacao.exportar_csv(df, brutos)

    # 3) Classificação do estágio operacional
    ind = estagios.indicadores_dos_brutos(brutos)
    resultado = estagios.classificar_estagio(ind, infra=infra)

    # 4) Snapshot p/ dashboard
    serie_guaiba = brutos["rios"].get("Guaiba_PortoAlegre_CaisMaua", pd.DataFrame())
    horaria = brutos["meteo"].get("horaria", pd.DataFrame())
    diaria = brutos["meteo"].get("diaria", pd.DataFrame())

    def _sem_nan(df_: pd.DataFrame) -> pd.DataFrame:
        """NaN → None: NaN não é JSON válido e congela o dashboard no navegador."""
        return df_.astype(object).where(pd.notnull(df_), None)

    df = _sem_nan(df)
    serie_guaiba = _sem_nan(serie_guaiba) if not serie_guaiba.empty else serie_guaiba
    horaria = _sem_nan(horaria) if not horaria.empty else horaria
    diaria = _sem_nan(diaria) if not diaria.empty else diaria

    # Na primeira execução, baixa um ano em blocos de 30 dias (limite da API
    # telemétrica da ANA). Depois, o CSV persistido recebe apenas a coleta
    # recente, evitando repetir o bootstrap em cada atualização do painel.
    historico_bootstrap = {}
    if not alinhamento_afluentes.historico_suficiente():
        nomes_modelo = [
            "Guaiba_PortoAlegre_CaisMaua",
            *config.AFLUENTES_GUAIBA.keys(),
        ]
        print("[MODELO GUAÍBA] Histórico insuficiente; baixando 365 dias...")
        try:
            historico_bootstrap = ana_api.coletar_niveis_rios(
                dias=config.DIAS_HISTORICO_MODELO_GUAIBA,
                nomes=nomes_modelo)
        except Exception as exc:
            print(f"[MODELO GUAÍBA] Bootstrap histórico falhou: {exc}")

    historico_modelo = alinhamento_afluentes.atualizar_historico(
        brutos["rios"], historico_bootstrap)

    # Séries dos quatro afluentes + previsão histórica do Guaíba.
    series_afluentes = alinhamento_afluentes.preparar_series_afluentes(
        brutos["rios"], historico=historico_modelo)

    # ── Status de cada fonte nesta coleta (mostrado no painel) ──
    poa = brutos.get("poaclima") or {}
    niveis_poa = poa.get("niveis") or {}
    fontes = {
        "ANA": any(not df.empty for df in brutos["rios"].values()),
        "Open-Meteo": not brutos["meteo"].get("horaria", pd.DataFrame()).empty,
        "INMET": (brutos.get("inmet") or {}).get("consultado", True),
        # Duas camadas, duas flags. Antes era um OU: bastava os NÍVEIS virem
        # para o Poaclima ser dado como "ok", mesmo que a camada de ALERTAS
        # tivesse falhado — e a grade das 17 regiões então mostrava
        # "sem alerta" (verdadeiro-negativo aparente) quando o certo era
        # "sem dado". Uma falha de coleta não pode se disfarçar de ausência
        # de risco num painel de contingência.
        # NÃO usar a lista de alertas como prova de sucesso: quando o
        # alerta vence (o de 29/07 expirou às 15:00), a lista fica vazia e
        # o painel passava a dizer "não foi possível consultar" num dia
        # perfeitamente normal. Um aviso que aparece todo dia calmo deixa
        # de ser lido justamente no dia em que importa. Quem responde se a
        # camada foi lida é o scraper.
        "Poaclima · alertas": bool(poa.get("alertas_consultados")),
        "Poaclima · níveis": any(v is not None for v in niveis_poa.values()),
        # Só conta como fonte OK quando a página foi lida E interpretada:
        # 200 com lista vazia é falha silenciosa, não dia sem aviso.
        "Defesa Civil · avisos": bool(
            (brutos.get("avisos_defesa_civil") or {}).get("estrutura_ok")),
    }
    falhas = [n for n, ok in fontes.items() if not ok]
    if falhas:
        print(f"[PIPELINE] ⚠ Fontes SEM dados nesta coleta: {', '.join(falhas)}")

    snapshot = {
        "timestamp": brutos["timestamp"].strftime("%d/%m/%Y %H:%M"),
        # ISO para o JS medir há quanto tempo a coleta rodou e avisar
        # quando o painel estiver velho (cron do Actions falha às vezes)
        "timestamp_iso": brutos["timestamp"].isoformat(),
        "fontes": fontes,
        "gatilhos_ativos": [r for _, r in estagios.gatilhos_ativos(infra)],
        # Avisos da Defesa Civil de POA: fonte de DESTAQUE do painel. Os do
        # INMET seguem no snapshot, mas entram como complemento — duas
        # escalas de cor para o mesmo céu geram dúvida na hora de decidir.
        "avisos_defesa_civil": brutos.get("avisos_defesa_civil") or {
            "vigentes": [], "ultimo": None, "consultado": False},
        "avisos_inmet": {
            "alertas": (brutos.get("inmet") or {}).get("alertas", []),
            "max_severidade": (brutos.get("inmet") or {}).get("max_severidade"),
            "consultado": (brutos.get("inmet") or {}).get("consultado", True),
            "fonte": (brutos.get("inmet") or {}).get("fonte"),
        },
        "csv_exportado": caminho_csv,
        # de qual régua saiu o número do card do Guaíba nesta coleta
        "fonte_nivel_guaiba": brutos.get("fonte_nivel_guaiba"),
        "classificacao": {k: v for k, v in resultado.items() if k != "detalhes"},
        "detalhes": resultado["detalhes"],
        "indicadores": asdict(ind) | {
            "afluentes": {k: {kk: (str(vv) if hasattr(vv, "isoformat") else vv)
                              for kk, vv in v.items()}
                          for k, v in ind.afluentes.items()}
        },
        "tabela": df.to_dict("records"),
        "serie_guaiba": (serie_guaiba.assign(
            datahora=serie_guaiba["datahora"].astype(str))
            .to_dict("records") if not serie_guaiba.empty else []),
        "series_afluentes": series_afluentes,
        # ── CHUVA OBSERVADA (fonte única, já auditada) ──
        "chuva_obs_inmet": (
            brutos["chuva_obs"]["horaria"]
            .assign(datahora=lambda d: d["datahora"].astype(str))
            .to_dict("records")
            if (brutos.get("chuva_obs", {}).get("ok")
                and not brutos["chuva_obs"]["horaria"].empty) else []),
        "serie_obs_diaria": (
            brutos["chuva_obs"]["diaria"]
            .assign(data=lambda d: d["data"].astype(str))
            .to_dict("records")
            if (brutos.get("chuva_obs", {}).get("ok")
                and not brutos["chuva_obs"]["diaria"].empty) else []),
        "fonte_chuva_obs": (brutos.get("chuva_obs", {}).get("fonte_curta")
                            or brutos.get("chuva_obs", {}).get("fonte")
                            or "Open-Meteo"),
        "qualidade_chuva_obs": (
            (brutos.get("chuva_obs", {}).get("qualidade") or {})),
        "fontes_chuva_testadas": (
            brutos.get("chuva_obs", {}).get("tentativas") or []),
        "previsao_poaclima": [
            {**d, "data": str(d["data"])}
            for d in (brutos.get("previsao_poaclima", {}) or {}).get("dias", [])],
        # Horário do BOLETIM da Catavento — diferente do horário da nossa
        # coleta. Os cards de previsão mostram este, para não parecerem
        # mais recentes do que a origem realmente é.
        "previsao_atualizada_em": (
            (brutos.get("previsao_poaclima", {}) or {}).get("atualizado_em")),
        # card de chuva: 5 dias para trás × 5 dias para frente
        # Cards de chuva: janela de 3 DIAS dos dois lados. Simetria importa
        # — comparar 5 dias de chuva já caída com 5 dias de previsão dá peso
        # igual a um número medido e a um número modelado.
        "chuva_obs_3d_mm": ind.acumulado_obs_72h_mm,
        "chuva_prev_3d_mm": ind.previsto_72h_mm,
        "chuva_obs_5d_mm": ind.acumulado_obs_5d_mm,
        "chuva_prev_5d_mm": ind.previsto_5d_mm,
        "fonte_chuva_prev": ("Poaclima/Catavento"
                             if (brutos.get("previsao_poaclima", {}) or {}).get("ok")
                             else "Open-Meteo"),
        "serie_precipitacao_horaria": (horaria.assign(
            datahora=horaria["datahora"].astype(str))
            .to_dict("records") if not horaria.empty else []),
        "serie_precipitacao_diaria": (diaria.assign(
            data=diaria["data"].astype(str))
            .to_dict("records") if not diaria.empty else []),
    }

    caminho_json = config.DADOS_DIR / "ultimo_snapshot.json"

    def _json_seguro(obj):
        """Converte NaN residual em None na serialização final."""
        import math
        if isinstance(obj, float) and math.isnan(obj):
            return None
        return str(obj)

    texto = json.dumps(snapshot, ensure_ascii=False, default=_json_seguro)
    texto = texto.replace(": NaN", ": null").replace(":NaN", ":null")
    caminho_json.write_text(texto, encoding="utf-8")
    print(f"[PIPELINE] Snapshot salvo em {caminho_json}")
    print(f"[PIPELINE] >>> ESTÁGIO OPERACIONAL: {resultado['estagio']} <<<")
    for j in resultado["justificativas"]:
        print(f"           • {j}")
    return snapshot


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Estágios Operacionais POA")
    parser.add_argument("--sem-selenium", action="store_true",
                        help="pula os scrapers Selenium (INMET/Poaclima)")
    args = parser.parse_args()
    executar_pipeline(usar_selenium=not args.sem_selenium)
