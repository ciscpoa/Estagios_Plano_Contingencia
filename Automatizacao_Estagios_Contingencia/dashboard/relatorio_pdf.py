# -*- coding: utf-8 -*-
"""
relatorio_pdf.py
================
Geração de PDF NO SERVIDOR (sem depender do diálogo do navegador):
paisagem A4, layout controlado, cores garantidas.

Estrutura do relatório:
  1. Cabeçalho (título + CISC + data/hora da extração)
  2. Banner do ESTÁGIO OPERACIONAL (cor do estágio) + justificativas
  3. Tabela dos rios: nível × cota de inundação × % (célula colorida)
  4. Grid das 17 regiões (risco Defesa Civil/Poaclima, células coloridas)
  5. Gráficos (kaleido → PNG, tema claro): Guaíba, afluentes, precipitação
  6. Rodapé (cotas de referência + disclaimer)

Uso:  gerar_relatorio_pdf(snapshot) -> caminho do PDF gerado
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

import config

_LARG, _ALT = landscape(A4)
_UTIL = _LARG - 24 * mm  # largura útil (margens 12mm)

_ST_TITULO = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=17,
                            leading=21, alignment=1, spaceAfter=4)
_ST_SUB = ParagraphStyle("sub", fontName="Helvetica", fontSize=9.5,
                         leading=12, alignment=1, spaceAfter=2,
                         textColor=colors.HexColor("#5A6472"))
_ST_BANNER = ParagraphStyle("banner", fontName="Helvetica-Bold", fontSize=16,
                            leading=20, alignment=1, textColor=colors.white)
_ST_JUST = ParagraphStyle("just", fontName="Helvetica", fontSize=9,
                          alignment=1, textColor=colors.white, leading=12)
_ST_H = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=11,
                       leading=14, alignment=1, spaceBefore=6, spaceAfter=3)
_ST_CEL = ParagraphStyle("cel", fontName="Helvetica", fontSize=8,
                         alignment=1, leading=9.5)
_ST_CEL_B = ParagraphStyle("celb", fontName="Helvetica-Bold", fontSize=8.5,
                           alignment=1, textColor=colors.white, leading=10)
_ST_RODAPE = ParagraphStyle("rod", fontName="Helvetica", fontSize=8,
                            alignment=1, textColor=colors.HexColor("#5A6472"))
_ST_CISC = ParagraphStyle("cisc", fontName="Helvetica-Bold", fontSize=10,
                          leading=13, alignment=1, spaceBefore=6)


def _cor_pct(pct: float | None) -> colors.Color:
    if pct is None:
        return colors.HexColor("#8B95A1")
    if pct >= 100:
        return colors.HexColor(config.CORES_ESTAGIOS["SITUAÇÃO DE EMERGÊNCIA"])
    if pct >= 85:
        return colors.HexColor(config.CORES_ESTAGIOS["ALERTA"])
    if pct >= 65:
        return colors.HexColor(config.CORES_ESTAGIOS["MOBILIZAÇÃO"])
    return colors.HexColor(config.CORES_ESTAGIOS["NORMALIDADE"])


def _cor_risco(risco: str | None) -> colors.Color:
    r = (risco or "").lower()
    if "extremo" in r:
        return colors.HexColor(config.CORES_RISCO_POACLIMA["extremo"])
    if "muito alto" in r:
        return colors.HexColor(config.CORES_RISCO_POACLIMA["muito alto"])
    if "alto" in r:
        return colors.HexColor(config.CORES_RISCO_POACLIMA["alto"])
    if "atenção" in r or "atencao" in r:
        return colors.HexColor(config.CORES_RISCO_POACLIMA["atenção"])
    if "sem risco" in r:
        return colors.HexColor(config.CORES_RISCO_POACLIMA["sem risco"])
    return colors.HexColor(config.CORES_RISCO_POACLIMA["sem dado"])


# ──────────────────────────────────────────────────────────────────────────
def _bloco_banner(snapshot: dict) -> Table:
    cls = snapshot.get("classificacao", {})
    cor = colors.HexColor(cls.get("cor", "#2E9E44"))
    linhas = [[Paragraph(f"ESTÁGIO OPERACIONAL: {cls.get('estagio', '—')}",
                         _ST_BANNER)],
              [Paragraph(f"Última atualização: {snapshot.get('timestamp', '—')}",
                         _ST_JUST)]]
    for j in cls.get("justificativas", [])[:6]:
        linhas.append([Paragraph("• " + j, _ST_JUST)])
    t = Table(linhas, colWidths=[_UTIL])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    return t


def _bloco_rios(snapshot: dict) -> Table:
    ind = snapshot.get("indicadores", {}) or {}
    afl = ind.get("afluentes") or {}

    def nivel_de(chave):
        if chave == "Guaiba_PortoAlegre_CaisMaua":
            return ind.get("nivel_guaiba_m")
        if chave == "poaclima_gasometro":
            return ind.get("poaclima_gasometro_m")
        if chave == "poaclima_cais_maua":
            return ind.get("poaclima_cais_maua_m")
        d = afl.get(chave) or {}
        return d.get("nivel_atual_m") if d.get("nivel_atual_m") is not None \
            else d.get("nivel_m")

    cab = [Paragraph(f"<b>{c}</b>", _ST_CEL) for c in
           ("Rio", "Município", "Estação", "Nível", "Cota inund.", "% da cota")]
    linhas, estilos = [cab], []
    i = 0
    for info in config.INFO_RIOS_CARDS:
        cota = info["cota_inundacao"]
        i += 1
        nivel = nivel_de(info["chave"])
        pct = (nivel / cota * 100.0) if (nivel is not None and cota) else None
        linhas.append([
            Paragraph(info["rotulo"], _ST_CEL),
            Paragraph(info["municipio"], _ST_CEL),
            Paragraph(str(info["estacao"]), _ST_CEL),
            Paragraph(f"{nivel:.2f} m" if nivel is not None else "—", _ST_CEL),
            Paragraph(f"{cota:.2f} m" if cota else "não informada", _ST_CEL),
            Paragraph(f"{pct:.0f}%" if pct is not None else "—", _ST_CEL_B),
        ])
        estilos.append(("BACKGROUND", (5, i), (5, i), _cor_pct(pct)))

    t = Table(linhas, colWidths=[_UTIL * f for f in
                                 (0.16, 0.24, 0.18, 0.14, 0.14, 0.14)])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D0D8")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF1F5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ] + estilos))
    return t


def _bloco_regioes(snapshot: dict) -> Table:
    alertas = (snapshot.get("indicadores", {}) or {}).get("alertas_regionais") or []
    por_regiao: dict[int, dict] = {}
    for al in alertas:
        n = al.get("regiao_num")
        if n is not None:
            por_regiao.setdefault(n, al)

    celulas, estilos = [], []
    grade = [list(range(1, 7)), list(range(7, 13)), list(range(13, 18)) + [None]]
    for li, linha in enumerate(grade):
        row = []
        for ci, num in enumerate(linha):
            if num is None:
                row.append("")
                continue
            al = por_regiao.get(num)
            nome = (al or {}).get("regiao_nome") or config.REGIOES_POACLIMA.get(num, "")
            status = (al or {}).get("risco") or "sem dado"
            extra = ""
            if al and al.get("tipo"):
                extra = f"<br/>{al['tipo']}" + (f" · até {al['fim']}" if al.get("fim") else "")
            row.append(Paragraph(f"<b>{num} · {nome}</b><br/>{status}{extra}",
                                 _ST_CEL_B))
            estilos.append(("BACKGROUND", (ci, li), (ci, li),
                            _cor_risco((al or {}).get("risco"))))
        celulas.append(row)

    t = Table(celulas, colWidths=[_UTIL / 6] * 6, rowHeights=[15 * mm] * 3)
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 1.2, colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ] + estilos))
    return t


def _imagens_graficos(snapshot: dict) -> list:
    """Renderiza os gráficos (tema claro) via kaleido; pula se indisponível."""
    try:
        from dashboard import componentes
        figs = [
            ("guaiba", componentes.grafico_guaiba(
                snapshot.get("serie_guaiba", []), "claro"), 0.5),
            ("afluentes", componentes.grafico_afluentes(
                snapshot.get("series_afluentes", {}), "claro"), 0.5),
            ("chuva", componentes.grafico_precipitacao(
                snapshot.get("serie_precipitacao_horaria", []),
                snapshot.get("serie_precipitacao_diaria", []), "claro"), 1.0),
        ]
        elementos, linha = [], []
        for nome, fig, fracao in figs:
            fig.update_layout(paper_bgcolor="white", plot_bgcolor="white")
            largura_px = int(1000 * fracao) if fracao == 1.0 else 620
            png = fig.to_image(format="png", width=largura_px, height=340, scale=2)
            img = Image(BytesIO(png), width=_UTIL * fracao - (4 if fracao < 1 else 0),
                        height=(_UTIL * fracao - (4 if fracao < 1 else 0)) * 340 / largura_px)
            if fracao < 1.0:
                linha.append(img)
                if len(linha) == 2:
                    t = Table([linha], colWidths=[_UTIL / 2] * 2)
                    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
                    elementos += [Spacer(1, 4), t]
                    linha = []
            else:
                elementos += [Spacer(1, 4), img]
        return elementos
    except Exception as exc:
        print(f"[PDF] Gráficos indisponíveis ({exc}); PDF segue sem eles. "
              "Instale 'kaleido' para incluir os gráficos.")
        return [Spacer(1, 4), Paragraph(
            "(gráficos omitidos — instale o pacote 'kaleido' para incluí-los)",
            _ST_RODAPE)]


# ──────────────────────────────────────────────────────────────────────────
def gerar_relatorio_pdf(snapshot: dict, caminho=None) -> str:
    ts = datetime.now()
    caminho = caminho or (config.ARQUIVOS_DIR /
                          f"relatorio_estagio_{ts:%Y%m%d_%H%M}.pdf")

    doc = SimpleDocTemplate(str(caminho), pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm,
                            title="Estágios Operacionais — Porto Alegre")

    fluxo = [
        Paragraph("Plano de Contingência — Estágios Operacionais", _ST_TITULO),
        Paragraph("Porto Alegre/RS · SMS/PMPA · monitoramento automatizado "
                  "(ANA · Open-Meteo · INMET · Poaclima)", _ST_SUB),
        Spacer(1, 5),
        _bloco_banner(snapshot),
        Spacer(1, 6),
        Paragraph("Níveis dos rios × cotas de inundação", _ST_H),
        _bloco_rios(snapshot),
        Spacer(1, 6),
        Paragraph("Risco por região — Defesa Civil (Poaclima)", _ST_H),
        _bloco_regioes(snapshot),
    ]
    fluxo += _imagens_graficos(snapshot)
    fluxo += [
        Spacer(1, 6),
        Paragraph("Realizado por: CISC Porto Alegre — Centro de Informações "
                  "em Saúde e Clima", _ST_CISC),
        Paragraph(
            f"Cotas de referência (Guaíba/Cais Mauá): Atenção "
            f"{config.COTA_ATENCAO_GUAIBA} m · Alerta {config.COTA_ALERTA_GUAIBA} m · "
            f"Inundação {config.COTA_INUNDACAO_GUAIBA} m. Ferramenta de apoio à "
            "decisão — não substitui os canais oficiais da Defesa Civil.",
            _ST_RODAPE),
    ]
    doc.build(fluxo)
    print(f"[PDF] Relatório gerado: {caminho}")
    return str(caminho)
