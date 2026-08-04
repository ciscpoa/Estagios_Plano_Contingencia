# -*- coding: utf-8 -*-
"""
publicacao.py
=============
Guarda de publicação: decide se o snapshot NOVO pode substituir o anterior.

O problema que este módulo resolve
----------------------------------
Quando a ANA não responde, os níveis dos rios chegam vazios. A classificação
então roda sem o sinal hidrológico e cai para NORMALIDADE (verde) — e o
painel, que dez minutos antes mostrava MOBILIZAÇÃO, aparece tranquilo com um
"Última atualização" recém-carimbado. Falha de coleta virou notícia boa.

Num painel de contingência isso é o pior erro possível: o dado ausente se
disfarça de dado favorável, e o carimbo de hora dá a ele a aparência de
recém-conferido.

A regra
-------
Coleta da ANA degradada → NÃO grava nada por cima. O painel inteiro fica
como estava: cards, estágio, gráficos e o "Última atualização" do último
ciclo que deu certo. Só é anotado, no próprio snapshot, que houve uma
tentativa malsucedida — para a página poder dizer isso em voz baixa, sem
mexer no conteúdo.

Duas exceções, ambas de segurança
---------------------------------
1. AGRAVAMENTO. Se mesmo sem a ANA a classificação subir de estágio (chuva
   extrema, aviso vermelho do INMET, gatilho de campo confirmado), publica.
   Congelar seria esconder uma piora — exatamente o contrário do objetivo.

2. VALIDADE. Congelamento não é eterno. Passadas `horas_max_congelado`, o
   snapshot velho deixa de ser informação e passa a ser ilusão: publica o
   novo, que já vem com o aviso de fontes fora e, quando é o caso, com o
   rótulo DADOS INSUFICIENTES.

Parâmetros em config.CONGELAR_COLETA_INCOMPLETA.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

import config

CHAVE_GUAIBA = "Guaiba_PortoAlegre_CaisMaua"


@dataclass
class Veredito:
    congelar: bool = False
    motivo: str = ""
    estacoes_ok: int = 0
    estacoes_antes: int | None = None
    idade_anterior_h: float | None = None
    excecoes: list = field(default_factory=list)

    def resumo(self) -> str:
        partes = [self.motivo] if self.motivo else []
        partes += self.excecoes
        return " · ".join(partes)


# ──────────────────────────────────────────────────────────────────────────
# leitura do snapshot anterior
# ──────────────────────────────────────────────────────────────────────────
def carregar_snapshot(caminho: str | Path) -> dict | None:
    caminho = Path(caminho)
    if not caminho.exists():
        return None
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[PUBLICAÇÃO] Snapshot anterior ilegível ({exc}); segue sem ele.")
        return None


def _idade_h(snapshot: dict | None) -> float | None:
    """Horas desde a última coleta BEM-SUCEDIDA registrada no snapshot."""
    if not snapshot:
        return None
    iso = snapshot.get("timestamp_iso")
    if not iso:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(iso)).total_seconds() / 3600
    except Exception:
        return None


def contar_estacoes_com_dados(rios: dict) -> int:
    """Estações da ANA que voltaram com pelo menos um nível legível."""
    total = 0
    for df in (rios or {}).values():
        if isinstance(df, pd.DataFrame) and not df.empty:
            if "nivel_m" in df.columns:
                if pd.to_numeric(df["nivel_m"], errors="coerce").notna().any():
                    total += 1
            else:
                total += 1
    return total


# ──────────────────────────────────────────────────────────────────────────
# avaliação
# ──────────────────────────────────────────────────────────────────────────
def avaliar(brutos: dict, snapshot_novo: dict,
            anterior: dict | None) -> Veredito:
    cfg = getattr(config, "CONGELAR_COLETA_INCOMPLETA", None) or {}
    estacoes_ok = contar_estacoes_com_dados(brutos.get("rios") or {})
    estacoes_antes = (anterior or {}).get("estacoes_ana_ok")
    v = Veredito(estacoes_ok=estacoes_ok, estacoes_antes=estacoes_antes,
                 idade_anterior_h=_idade_h(anterior))

    if not cfg.get("ativo", True):
        return v
    if not anterior:
        return v      # primeira execução: não há o que preservar

    configuradas = len(getattr(config, "ESTACOES_ANA", {}) or {})
    minimo = int(cfg.get("min_estacoes_ana", 2))
    fracao = float(cfg.get("fracao_minima_vs_anterior", 0.6))

    # ── 1. o que está faltando? ──────────────────────────────────────────
    if estacoes_ok == 0:
        v.motivo = "a ANA não devolveu nenhuma estação"
    elif estacoes_ok < minimo:
        v.motivo = (f"a ANA devolveu apenas {estacoes_ok} de {configuradas} "
                    f"estações")
    elif estacoes_antes and estacoes_ok < max(minimo, round(estacoes_antes * fracao)):
        v.motivo = (f"a ANA devolveu {estacoes_ok} estações contra "
                    f"{estacoes_antes} na coleta anterior")

    if cfg.get("exigir_nivel_guaiba", True):
        nivel = ((snapshot_novo.get("indicadores") or {})
                 .get("nivel_guaiba_m"))
        if nivel is None:
            v.motivo = v.motivo or "o nível do Guaíba não veio em nenhuma fonte"

    if not v.motivo:
        return v      # coleta saudável: publica normalmente

    # ── 2. exceção do AGRAVAMENTO ────────────────────────────────────────
    idx_novo = (snapshot_novo.get("classificacao") or {}).get("indice")
    idx_antes = (anterior.get("classificacao") or {}).get("indice")
    if isinstance(idx_novo, int) and isinstance(idx_antes, int) and idx_novo > idx_antes:
        v.excecoes.append(
            f"mesmo assim o estágio SUBIU ({config.ESTAGIOS[idx_antes]} → "
            f"{config.ESTAGIOS[idx_novo]}); publicando")
        return v

    # ── 3. exceção da VALIDADE ───────────────────────────────────────────
    teto_h = float(cfg.get("horas_max_congelado", 6))
    if v.idade_anterior_h is not None and v.idade_anterior_h > teto_h:
        v.excecoes.append(
            f"o painel congelado já tem {v.idade_anterior_h:.1f} h "
            f"(teto de {teto_h:.0f} h); publicando o dado incompleto")
        return v

    v.congelar = True
    return v


# ──────────────────────────────────────────────────────────────────────────
# congelamento
# ──────────────────────────────────────────────────────────────────────────
def congelar(caminho: str | Path, anterior: dict, veredito: Veredito,
             agora: datetime | None = None) -> dict:
    """
    Regrava o snapshot ANTERIOR, intocado, com uma única adição: o registro
    da tentativa que falhou. Nada de conteúdo muda — nem o timestamp.
    """
    agora = agora or datetime.now()
    anteriores = (anterior.get("coleta_congelada") or {}).get("tentativas", 0)
    congelado = dict(anterior)
    congelado["coleta_congelada"] = {
        "motivo": veredito.motivo,
        "tentativa_em": agora.strftime("%d/%m/%Y %H:%M"),
        "tentativa_iso": agora.isoformat(),
        "tentativas": int(anteriores) + 1,
        "estacoes_ok": veredito.estacoes_ok,
        "estacoes_antes": veredito.estacoes_antes,
    }
    caminho = Path(caminho)
    texto = json.dumps(congelado, ensure_ascii=False, default=str)
    texto = texto.replace(": NaN", ": null").replace(":NaN", ":null")
    caminho.write_text(texto, encoding="utf-8")
    return congelado
