# -*- coding: utf-8 -*-
"""
Avisos e alertas publicados pela DEFESA CIVIL DE PORTO ALEGRE.

Por que esta fonte e não a do INMET no topo do painel: o INMET compõe a
análise, mas deixou de ser a fonte principal desde 2025. Ter o aviso do
INMET em destaque criava divergência de cor com o que a Defesa Civil de
POA publica — e num painel de contingência duas escalas de cor para o
mesmo céu viram dúvida na hora de decidir. O aviso municipal passa a ser
o destaque; o do INMET fica como complemento.

A página é HTML estático (Drupal), então aqui não entra Selenium: uma
requisição simples basta e o scraper roda mesmo com o navegador fora.

Estrutura lida (a mesma desde 2024):

    ### Alertas emitidos em 2026:
    **JANEIRO**
    Sem alertas para o período.
    ...
    **JUNHO**
    [Alerta para chuva intensa - 12/06](url da notícia)

Ou seja: o ANO vem no título da seção, o MÊS num parágrafo em negrito e
cada aviso é um link cujo texto termina em "- dd/mm". O ano nunca aparece
no texto do link, por isso ele é herdado da seção — sem isso um aviso de
janeiro cairia no ano errado na virada.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

URL_AVISOS_DEFESA_CIVIL = os.environ.get(
    "URL_AVISOS_DEFESA_CIVIL",
    "https://prefeitura.poa.br/defesa-civil/avisos-e-alertas")

# Janela de vigência: um aviso publicado hoje ou ontem ainda orienta a
# operação de hoje. Mais do que isso vira histórico — e histórico exibido
# como se fosse vigente é pior do que não exibir nada.
VIGENCIA_DIAS = 2

TIMEOUT_S = 20

# User-agent de navegador: com um agente "de robô" o portal pode responder
# 200 com uma página de bloqueio em vez do conteúdo — e aí a leitura volta
# vazia sem erro nenhum, que é o pior tipo de falha.
_CABECALHOS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

_MESES = {
    "janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5,
    "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
    "novembro": 11, "dezembro": 12,
}
_RE_ANO = re.compile(r"alertas\s+emitidos\s+em\s+(20\d{2})", re.I)
_RE_DATA = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})")
# "Alerta laranja para chuva intensa" — só usamos a cor quando ela está
# escrita. Deduzir severidade a partir do texto seria inventar um dado que
# a Defesa Civil não publicou naquele aviso.
_RE_COR = re.compile(r"\b(vermelh[oa]|laranja|amarel[oa])\b", re.I)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto)
                   if unicodedata.category(c) != "Mn").lower().strip()


def _limpar_titulo(texto: str) -> str:
    """'Alerta para chuva intensa - 12/06' → 'Alerta para chuva intensa'."""
    t = re.sub(r"[-–—]?\s*\d{1,2}\s*/\s*\d{1,2}\s*$", "", texto).strip()
    return re.sub(r"\s{2,}", " ", t).strip(" -–—·")


def _parse_pagina(html: str) -> list[dict]:
    """
    Percorre o documento em ordem, herdando ano da seção e mês do parágrafo.

    A varredura é feita sobre `descendants` — cada texto e cada link na
    ordem em que aparecem — e não elemento a elemento. A versão anterior
    iterava por tags e devolvia zero na página real: no HTML da prefeitura
    os meses e os links não moram na mesma tag que o parser esperava, e um
    <div> externo que embrulha tudo casava com o ano de 2024 antes de
    qualquer aviso. Andar pelo documento linearizado não depende de onde a
    prefeitura resolveu abrir e fechar as tags.
    """
    sopa = BeautifulSoup(html, "html.parser")
    avisos: list[dict] = []
    ano_atual: int | None = None
    mes_atual: int | None = None

    def _marcar(texto: str) -> None:
        nonlocal ano_atual, mes_atual
        m_ano = _RE_ANO.search(texto)
        if m_ano:
            ano_atual = int(m_ano.group(1))
            return
        chave = _sem_acento(texto).strip(" :*.-–—")
        if chave in _MESES:
            mes_atual = _MESES[chave]

    for no in sopa.descendants:
        if isinstance(no, NavigableString):
            texto = str(no).strip()
            if texto:
                _marcar(texto)
            continue
        if not isinstance(no, Tag):
            continue
        # Cabeçalho de ano e rótulo de mês também são lidos pela tag
        # inteira: cobre o caso de o ano vir quebrado em <strong> no meio
        # da frase, quando nenhum nó de texto sozinho traz a frase toda.
        if no.name in ("h1", "h2", "h3", "h4", "strong", "b"):
            _marcar(no.get_text(" ", strip=True))
            continue
        if no.name != "a" or not no.get("href"):
            continue

        rotulo = no.get_text(" ", strip=True)
        alvo = _sem_acento(rotulo)
        if not rotulo or ("alerta" not in alvo and "aviso" not in alvo):
            continue
        # Sem ano explícito na página não se registra nada. Deduzir o ano
        # seria o pior erro possível aqui: um aviso de 2024 carimbado com o
        # ano corrente entraria no painel como alerta VIGENTE.
        if ano_atual is None or mes_atual is None:
            continue

        # A data pode estar no próprio link ou continuar logo depois
        # dele — em 2025 um aviso ficou partido em dois links, com o
        # texto terminando em "- 26/0" e o "7" no link seguinte.
        vizinho = BeautifulSoup(
            "".join(str(s) for s in no.next_siblings)[:60],
            "html.parser").get_text(" ", strip=True)[:6]
        m_data = None
        for candidato in (rotulo, rotulo + vizinho):
            for m in _RE_DATA.finditer(candidato):
                if 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
                    m_data = m
            if m_data:
                break
        if not m_data:
            continue
        dia, mes = int(m_data.group(1)), int(m_data.group(2))
        try:
            quando = date(ano_atual, mes, dia)
        except ValueError:
            continue

        m_cor = _RE_COR.search(rotulo)
        avisos.append({
            "data": quando.isoformat(),
            "data_br": quando.strftime("%d/%m/%Y"),
            "titulo": _limpar_titulo(rotulo),
            "cor_declarada": _sem_acento(m_cor.group(1)) if m_cor else None,
            "url": no["href"],
            "ano": ano_atual,
        })

    # Deduplica: a mesma notícia às vezes aparece em dois links seguidos.
    vistos, unicos = set(), []
    for a in sorted(avisos, key=lambda x: x["data"], reverse=True):
        chave = (a["data"], a["url"])
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(a)
    return unicos


def coletar_avisos_defesa_civil(hoje: date | None = None) -> dict:
    """
    Retorna:
      {
        "vigentes": [ {data, data_br, titulo, cor_declarada, url}, ... ],
        "ultimo":   {...} | None,      # aviso mais recente já publicado
        "total":    int,               # avisos lidos na página inteira
        "total_ano": int,
        "consultado": bool,            # a página respondeu?
        "fonte": "Defesa Civil de Porto Alegre",
        "url": ...,
      }

    Lista vazia COM consultado=True significa "nenhum aviso vigente";
    lista vazia SEM a flag significa "não deu para saber". A distinção é a
    mesma já usada na camada de alertas do Poaclima e existe pelo mesmo
    motivo: falha de coleta não pode se disfarçar de ausência de risco.
    """
    hoje = hoje or date.today()
    resultado = {
        "vigentes": [], "ultimo": None, "total": 0, "total_ano": 0,
        "consultado": False, "estrutura_ok": False,
        "fonte": "Defesa Civil de Porto Alegre",
        "url": URL_AVISOS_DEFESA_CIVIL,
        "verificado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
    try:
        resposta = requests.get(
            URL_AVISOS_DEFESA_CIVIL, timeout=TIMEOUT_S, headers=_CABECALHOS)
        resposta.raise_for_status()
    except Exception as exc:
        print(f"[Defesa Civil] Falha ao consultar avisos: {exc}")
        return resultado

    html = resposta.text
    try:
        avisos = _parse_pagina(html)
    except Exception as exc:
        print(f"[Defesa Civil] Falha ao interpretar a página: {exc}")
        return resultado

    resultado["consultado"] = True
    resultado["total"] = len(avisos)
    resultado["total_ano"] = sum(1 for a in avisos if a["ano"] == hoje.year)
    # Zero avisos numa página que sempre teve dezenas não é "ano calmo": é
    # leitura que não funcionou — HTML mudou, ou o que voltou não foi a
    # página (bloqueio por user-agent devolve 200 com outro conteúdo).
    # Enquanto essa dúvida existir, o painel não pode dizer "sem aviso".
    resultado["estrutura_ok"] = len(avisos) > 0
    if not resultado["estrutura_ok"]:
        print(f"[Defesa Civil] ⚠ NENHUM aviso interpretado. Diagnóstico: "
              f"{len(html)} chars | 'Alertas emitidos' presente: "
              f"{'sim' if 'lertas emitidos' in html else 'NÃO'} | "
              f"links na página: {html.count('<a ')}")
        return resultado

    limite = hoje.toordinal() - (VIGENCIA_DIAS - 1)
    for a in avisos:
        quando = date.fromisoformat(a["data"])
        if quando > hoje:            # aviso datado no futuro: ainda vale
            resultado["vigentes"].append(a)
        elif quando.toordinal() >= limite:
            resultado["vigentes"].append(a)
    resultado["ultimo"] = avisos[0] if avisos else None

    ult = resultado["ultimo"]
    print(f"[Defesa Civil] {len(resultado['vigentes'])} aviso(s) vigente(s) | "
          f"{resultado['total']} lidos na página"
          + (f" | último: {ult['data_br']} — {ult['titulo']}" if ult else ""))
    return resultado
