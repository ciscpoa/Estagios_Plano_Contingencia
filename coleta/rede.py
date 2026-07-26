# -*- coding: utf-8 -*-
"""
rede.py
=======
Ajustes de rede compartilhados pelos coletores.

Por que existe: em runners de CI (GitHub Actions) e em alguns provedores,
o DNS devolve endereços IPv6 (registro AAAA) para sites do gov.br, mas a
rota IPv6 não funciona. O resultado é `ConnectionError` ou
`ConnectTimeoutError` mesmo com a internet OK — foi exatamente o que
derrubou a ANA e as APIs do INMET na coleta de 26/07/2026 13:58.

`forcar_ipv4()` faz o urllib3 (usado pelo `requests`) resolver apenas
endereços IPv4, o que costuma resolver esse tipo de falha.
"""

from __future__ import annotations

import socket

_ja_aplicado = False


def forcar_ipv4() -> None:
    """Faz todas as conexões do `requests`/urllib3 usarem apenas IPv4."""
    global _ja_aplicado
    if _ja_aplicado:
        return
    try:
        import urllib3.util.connection as conexao_urllib3
        conexao_urllib3.allowed_gai_family = lambda: socket.AF_INET
        _ja_aplicado = True
        print("[rede] Conexões HTTP restritas a IPv4 "
              "(evita timeouts de IPv6 em servidores gov.br).")
    except Exception as exc:      # pragma: no cover
        print(f"[rede] Não foi possível forçar IPv4 ({exc}); seguindo normal.")


def cabecalhos_navegador(referer: str | None = None) -> dict:
    """Headers que evitam bloqueio 403 em APIs públicas do governo."""
    cab = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/126.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Connection": "close",
    }
    if referer:
        cab["Referer"] = referer
    return cab
