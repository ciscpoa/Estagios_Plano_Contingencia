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
from processamento import consolidacao
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

    # Séries dos afluentes (Gravataí, Sinos, Caí, Jacuí) p/ o gráfico
    series_afluentes = {}
    for nome, serie in brutos["rios"].items():
        if nome == "Guaiba_PortoAlegre_CaisMaua" or serie is None or serie.empty:
            continue
        s = _sem_nan(serie)
        series_afluentes[nome] = (
            s.assign(datahora=s["datahora"].astype(str)).to_dict("records"))

    # ── Status de cada fonte nesta coleta (mostrado no painel) ──
    poa = brutos.get("poaclima") or {}
    niveis_poa = poa.get("niveis") or {}
    fontes = {
        "ANA": any(not df.empty for df in brutos["rios"].values()),
        "Open-Meteo": not brutos["meteo"].get("horaria", pd.DataFrame()).empty,
        "INMET": (brutos.get("inmet") or {}).get("consultado", True),
        "Poaclima": bool(poa.get("alertas_regionais")
                         or any(v is not None for v in niveis_poa.values())),
    }
    falhas = [n for n, ok in fontes.items() if not ok]
    if falhas:
        print(f"[PIPELINE] ⚠ Fontes SEM dados nesta coleta: {', '.join(falhas)}")

    snapshot = {
        "timestamp": brutos["timestamp"].strftime("%d/%m/%Y %H:%M"),
        "fontes": fontes,
        "gatilhos_ativos": [r for _, r in estagios.gatilhos_ativos(infra)],
        "avisos_inmet": {
            "alertas": (brutos.get("inmet") or {}).get("alertas", []),
            "max_severidade": (brutos.get("inmet") or {}).get("max_severidade"),
            "consultado": (brutos.get("inmet") or {}).get("consultado", True),
            "fonte": (brutos.get("inmet") or {}).get("fonte"),
        },
        "csv_exportado": caminho_csv,
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
        "fonte_chuva_obs": (brutos.get("chuva_obs", {}).get("fonte")
                            or "Open-Meteo"),
        "qualidade_chuva_obs": (
            (brutos.get("chuva_obs", {}).get("qualidade") or {})),
        "fontes_chuva_testadas": (
            brutos.get("chuva_obs", {}).get("tentativas") or []),
        "previsao_poaclima": [
            {**d, "data": str(d["data"])}
            for d in (brutos.get("previsao_poaclima", {}) or {}).get("dias", [])],
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
