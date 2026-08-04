# -*- coding: utf-8 -*-
"""
ana_api.py
==========
Consumo da API HidroWebService da ANA (Agência Nacional de Águas e
Saneamento Básico) para dados de estações TELEMÉTRICAS — nível do Guaíba
e afluentes.

Fluxo:
  1. Lê ID e Senha do arquivo local `ANA_API_ID_SENHA.txt` (formato flexível).
  2. Obtém token OAuth em  /EstacoesTelemetricas/OAUth/v1
  3. Consulta séries em     /EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1
     (fallback: .../HidroinfoanaSerieTelemetricaDetalhada/v1)

Documentação: https://www.ana.gov.br/hidrowebservice/swagger-ui/index.html
"""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

import config

_SESSION = requests.Session()
_TOKEN_CACHE: dict = {"token": None, "expira": None}

# Marca a ANA como fora do ar para NÃO repetir 4 tentativas de token em
# cada uma das 7 estações (foi o que fez a coleta levar 12 min em 26/07).
_ANA_INDISPONIVEL: dict = {"ate": None, "motivo": None}
JANELA_INDISPONIVEL_S = 600      # 10 min sem insistir


def _marcar_indisponivel(motivo: str) -> None:
    from datetime import datetime, timedelta
    _ANA_INDISPONIVEL["ate"] = datetime.now() + timedelta(seconds=JANELA_INDISPONIVEL_S)
    _ANA_INDISPONIVEL["motivo"] = motivo
    print(f"[ANA] Servidor marcado como INDISPONÍVEL por "
          f"{JANELA_INDISPONIVEL_S // 60} min — as demais estações serão "
          f"puladas nesta coleta ({motivo}).")


def _esta_indisponivel() -> str | None:
    from datetime import datetime
    if _ANA_INDISPONIVEL["ate"] and datetime.now() < _ANA_INDISPONIVEL["ate"]:
        return _ANA_INDISPONIVEL["motivo"]
    return None

# ── Política de resiliência (a HidroWebService oscila com frequência) ────
MAX_TENTATIVAS = 3          # tentativas por requisição
BACKOFF_BASE_S = 2          # espera: 2s, 4s, 8s...
# 417 EXPECTATION_FAILED: a ANA devolve esse código de forma transitória
# (observado no token OAuth) — retry resolve, então entra na lista.
STATUS_RETRY = {408, 417, 429, 500, 502, 503, 504}


def _get_com_retry(url: str, *, headers=None, params=None,
                   timeout: int = 60, contexto: str = "") -> requests.Response | None:
    """
    GET com até MAX_TENTATIVAS e backoff exponencial.
    Repete em: timeout, erro de conexão, 429 e 5xx.
    NÃO repete em 4xx (erro de requisição/credencial — repetir não resolve);
    devolve a Response para o chamador decidir (ex.: renovar token em 401).
    Retorna a Response, ou None se todas as tentativas falharem.
    """
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            r = _SESSION.get(url, headers=headers, params=params, timeout=timeout)
            if r.status_code in STATUS_RETRY:
                ultimo_erro = f"HTTP {r.status_code}"
            elif 400 <= r.status_code < 500:
                # erro do cliente (400/401/403/404...): retry não resolve.
                # A ANA devolve JSON com "message" explicando o motivo — logar!
                corpo = ""
                try:
                    corpo = r.text[:300].replace("\n", " ")
                except Exception:
                    pass
                print(f"[ANA]{contexto} HTTP {r.status_code} — sem retry. "
                      f"Resposta: {corpo}")
                return r          # o chamador decide (renovar token, pular etc.)
            else:
                r.raise_for_status()
                return r
        except requests.Timeout:
            ultimo_erro = "timeout"
        except requests.ConnectionError as exc:
            ultimo_erro = f"conexão ({exc.__class__.__name__})"
        except requests.RequestException as exc:
            ultimo_erro = str(exc)

        if tentativa < MAX_TENTATIVAS:
            espera = BACKOFF_BASE_S * (2 ** (tentativa - 1))
            print(f"[ANA]{contexto} tentativa {tentativa}/{MAX_TENTATIVAS} "
                  f"falhou ({ultimo_erro}); aguardando {espera}s...")
            time.sleep(espera)

    print(f"[ANA]{contexto} DESISTINDO após {MAX_TENTATIVAS} tentativas ({ultimo_erro}).")
    return None


# ──────────────────────────────────────────────────────────────────────────
# 1) CREDENCIAIS — leitura flexível do TXT
# ──────────────────────────────────────────────────────────────────────────
def ler_credenciais(caminho=None) -> tuple[str, str]:
    """
    Busca as credenciais da ANA nesta ordem (a 1ª encontrada vence):

      1. Variáveis de ambiente:  ANA_IDENTIFICADOR / ANA_SENHA
         (aliases aceitos: ANA_API_ID, ANA_ID, ANA_API_SENHA, ANA_PASSWORD)
         → ideal para o Render (Environment → Add Environment Variable)
      2. Secrets do Google Colab (ícone de chave 🔑 na barra lateral):
         chaves ANA_IDENTIFICADOR e ANA_SENHA
      3. Arquivo local `ANA_API_ID_SENHA.txt` (formato flexível)

    Retorna (identificador, senha).
    """
    import os

    # ── 1) Variáveis de ambiente ─────────────────────────────
    id_env = (os.environ.get("ANA_IDENTIFICADOR") or os.environ.get("ANA_API_ID")
              or os.environ.get("ANA_ID"))
    pw_env = (os.environ.get("ANA_SENHA") or os.environ.get("ANA_API_SENHA")
              or os.environ.get("ANA_PASSWORD"))
    if id_env and pw_env:
        return id_env.strip(), pw_env.strip()

    # ── 2) Secrets do Colab ──────────────────────────────────
    if config.IN_COLAB:
        try:
            from google.colab import userdata
            id_sec = pw_sec = None
            try:
                id_sec = userdata.get("ANA_IDENTIFICADOR")
            except Exception:
                pass
            try:
                pw_sec = userdata.get("ANA_SENHA")
            except Exception:
                pass
            if id_sec and pw_sec:
                print("[ANA] Credenciais carregadas dos Secrets do Colab 🔑")
                return id_sec.strip(), pw_sec.strip()
        except ImportError:
            pass

    # ── 3) Arquivo TXT ───────────────────────────────────────
    caminho = caminho or config.ANA_CREDENCIAIS_TXT
    if not caminho.exists():
        raise FileNotFoundError(
            f"Credenciais da ANA não encontradas. Defina as variáveis de "
            f"ambiente/Secrets ANA_IDENTIFICADOR e ANA_SENHA, ou crie o "
            f"arquivo: {caminho}"
        )

    linhas = [l.strip() for l in caminho.read_text(encoding="utf-8").splitlines() if l.strip()]

    def _limpar(valor: str) -> str:
        """Remove espaços, aspas simples/duplas e vírgula/; ao final.
        Aceita:  "XXXX"   'XXXX'   XXXX,   "XXXX";
        """
        v = valor.strip().rstrip(",;").strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        return v.strip()

    identificador, senha = None, None
    padrao = re.compile(r"^\s*(id|identificador|login|user|usuario)\s*[:=]\s*(.+)$", re.I)
    padrao_pw = re.compile(r"^\s*(senha|password|pass|pwd)\s*[:=]\s*(.+)$", re.I)

    for linha in linhas:
        m_id = padrao.match(linha)
        m_pw = padrao_pw.match(linha)
        if m_id:
            identificador = _limpar(m_id.group(2))
        elif m_pw:
            senha = _limpar(m_pw.group(2))

    # Fallback: primeiras duas linhas "puras"
    if identificador is None or senha is None:
        puras = [_limpar(l) for l in linhas if ":" not in l and "=" not in l]
        puras = [p for p in puras if p]
        if len(puras) >= 2:
            identificador = identificador or puras[0]
            senha = senha or puras[1]

    if not identificador or not senha:
        raise ValueError(
            "Não foi possível interpretar o ANA_API_ID_SENHA.txt. "
            "Use ID na 1ª linha e Senha na 2ª."
        )
    return identificador, senha


# ──────────────────────────────────────────────────────────────────────────
# 2) TOKEN OAUTH
# ──────────────────────────────────────────────────────────────────────────
def obter_token(force: bool = False) -> str:
    """Obtém (e cacheia) o token OAuth da HidroWebService."""
    from coleta.rede import forcar_ipv4
    forcar_ipv4()      # servidores gov.br + IPv6 de CI = timeout

    motivo = _esta_indisponivel()
    if motivo:
        raise RuntimeError(f"ANA indisponível nesta coleta ({motivo})")
    agora = datetime.now()
    if (not force and _TOKEN_CACHE["token"]
            and _TOKEN_CACHE["expira"] and agora < _TOKEN_CACHE["expira"]):
        return _TOKEN_CACHE["token"]

    identificador, senha = ler_credenciais()
    url = f"{config.ANA_BASE_URL}/EstacoesTelemetricas/OAUth/v1"
    resp = _get_com_retry(
        url,
        headers={"Identificador": identificador, "Senha": senha},
        timeout=30,
        contexto="[token]",
    )
    if resp is None:
        _marcar_indisponivel("falha ao obter token")
        raise RuntimeError("ANA fora do ar: não foi possível obter token "
                           f"após {MAX_TENTATIVAS} tentativas.")
    resp.raise_for_status()
    payload = resp.json()
    token = (payload.get("items") or {}).get("tokenautenticacao") or payload.get("token")
    if not token:
        raise RuntimeError(f"Resposta inesperada da ANA ao autenticar: {payload}")

    _TOKEN_CACHE["token"] = token
    # Token vale 60 min (manual ANA). Cache por 50 min: o manual alerta que
    # autenticações em alta frequência podem levar a BLOQUEIO de IP.
    _TOKEN_CACHE["expira"] = agora + timedelta(minutes=50)
    return token


# ──────────────────────────────────────────────────────────────────────────
# 3) SÉRIES TELEMÉTRICAS
# ──────────────────────────────────────────────────────────────────────────
# ── Dialetos de parâmetros da HidroWebService ────────────────────────────
# A documentação da ANA é ambígua: o Swagger exibe nomes com espaços/acentos
# ("Código da Estação") enquanto o exemplo Java do manual usa CamelCase
# ("CodigoDaEstacao"). O cliente testa os dialetos abaixo em ordem e MEMORIZA
# o primeiro que retornar 200, usando-o para as demais estações.
_DIALETO_OK: dict = {"indice": None}


def _dialetos_params(codigo_estacao: str,
                     data_busca: datetime | None = None) -> list[tuple[str, dict]]:
    data_txt = (data_busca or datetime.now()).strftime("%Y-%m-%d")
    return [
        ("swagger-espacos", {
            "Código da Estação": codigo_estacao,
            "Tipo Filtro Data": "DATA_LEITURA",
            "Data de Busca (yyyy-MM-dd)": data_txt,
            "Range Intervalo de busca": "DIAS_30",
        }),
        ("camelcase+data", {
            "CodigoDaEstacao": codigo_estacao,
            "TipoFiltroData": "DATA_LEITURA",
            "DataDeBusca": data_txt,
            "RangeIntervaloDeBusca": "DIAS_30",
        }),
        ("camelcase", {
            "CodigoDaEstacao": codigo_estacao,
            "TipoFiltroData": "DATA_LEITURA",
            "RangeIntervaloDeBusca": "DIAS_30",
        }),
        ("swagger-espacos-sem-range", {
            "Código da Estação": codigo_estacao,
            "Tipo Filtro Data": "DATA_LEITURA",
            "Data de Busca (yyyy-MM-dd)": data_txt,
        }),
    ]


def _consultar_janela_30d(codigo_estacao: str,
                          fim: datetime) -> pd.DataFrame:
    """
    Consulta a série telemétrica (adotada; fallback detalhada) da estação,
    testando os dialetos de parâmetros até um funcionar (e memorizando-o).
    A API telemétrica limita cada requisição a 30 dias.
    """
    token = obter_token()
    inicio = fim - timedelta(days=30)
    headers = {"Authorization": f"Bearer {token}"}

    dialetos = _dialetos_params(codigo_estacao, fim)
    # dialeto já validado vai primeiro
    if _DIALETO_OK["indice"] is not None:
        d = dialetos.pop(_DIALETO_OK["indice"])
        dialetos.insert(0, d)

    for endpoint in (
        "EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1",
        "EstacoesTelemetricas/HidroinfoanaSerieTelemetricaDetalhada/v1",
    ):
        for nome_dialeto, params in dialetos:
            ctx = f"[{codigo_estacao}/{endpoint.split('/')[-2][-8:]}/{nome_dialeto}]"
            r = _get_com_retry(f"{config.ANA_BASE_URL}/{endpoint}",
                               headers=headers, params=params, timeout=60,
                               contexto=ctx)
            if r is not None and r.status_code in (401, 403):
                # token expirou no meio → renova e repete a bateria de retries
                try:
                    headers["Authorization"] = f"Bearer {obter_token(force=True)}"
                except Exception as exc:
                    print(f"[ANA]{ctx} não foi possível renovar token: {exc}")
                    continue
                r = _get_com_retry(f"{config.ANA_BASE_URL}/{endpoint}",
                                   headers=headers, params=params, timeout=60,
                                   contexto=ctx)

            if r is None or not r.ok:
                continue  # 400 etc. → próximo dialeto
            try:
                items = r.json().get("items") or []
            except ValueError:
                print(f"[ANA]{ctx} resposta não-JSON; tentando próximo formato.")
                continue

            # requisição ACEITA (200) → memoriza o dialeto vencedor
            if _DIALETO_OK["indice"] is None:
                nomes = [n for n, _ in _dialetos_params("x", fim)]
                _DIALETO_OK["indice"] = nomes.index(nome_dialeto)
                print(f"[ANA] Dialeto de parâmetros validado: '{nome_dialeto}' "
                      f"(será usado nas próximas consultas).")
            if items:
                return _itens_para_df(items, inicio)
            print(f"[ANA]{ctx} 200 porém sem registros; tentando próximo endpoint.")
            break  # dialeto ok, mas endpoint sem dados → próximo endpoint

    return pd.DataFrame(columns=["datahora", "nivel_m", "chuva_mm"])


def _consultar_serie(codigo_estacao: str, dias: int = 7) -> pd.DataFrame:
    """Consulta até um ano em blocos de 30 dias e elimina as sobreposições."""
    dias = max(1, int(dias))
    fim_global = datetime.now()
    inicio_global = fim_global - timedelta(days=dias)
    partes = []
    for deslocamento in range(0, dias, 30):
        fim_janela = fim_global - timedelta(days=deslocamento)
        parte = _consultar_janela_30d(codigo_estacao, fim_janela)
        if not parte.empty:
            partes.append(parte)
    if not partes:
        return pd.DataFrame(columns=["datahora", "nivel_m", "chuva_mm"])
    serie = (
        pd.concat(partes, ignore_index=True)
        .drop_duplicates(subset=["datahora"], keep="last")
        .loc[lambda d: d["datahora"] >= inicio_global]
        .sort_values("datahora")
        .reset_index(drop=True)
    )
    # Filtro aplicado aqui, na série já completa e ordenada: cada consumidor
    # a jusante (cards, tendência 48h, gráficos, histórico) recebe os mesmos
    # dados limpos, sem precisar repetir a limpeza.
    return remover_picos(serie, rotulo=codigo_estacao)


def remover_picos(df: pd.DataFrame, rotulo: str = "") -> pd.DataFrame:
    """
    Descarta leituras isoladas fisicamente impossíveis (filtro de Hampel).

    O sensor do Cais Mauá manda, esporadicamente, valores ~1,3 m abaixo das
    leituras vizinhas — em 15 minutos o Guaíba não cai 1,3 m. O ponto vira
    vazio (None) em vez de sumir da série: assim o gráfico abre um buraco
    honesto na linha, em vez de ligar dois instantes distantes com um traço
    reto que dá a impressão de uma queda que não houve.

    Parâmetros em config.FILTRO_PICOS_ANA. Devolve uma CÓPIA.
    """
    cfg = getattr(config, "FILTRO_PICOS_ANA", None) or {}
    if not cfg.get("ativo", True) or df is None or df.empty:
        return df
    if "nivel_m" not in df.columns or "datahora" not in df.columns:
        return df

    # Só nas estações autorizadas (ver comentário no config): o filtro supõe
    # que a leitura boa é a maioria da janela, e isso não vale em toda régua.
    permitidas = cfg.get("estacoes")
    if permitidas:
        codigos = {str(config.ESTACOES_ANA[n]) for n in permitidas
                   if n in config.ESTACOES_ANA}
        codigos |= {str(n) for n in permitidas}
        if str(rotulo) not in codigos:
            return df

    valores = pd.to_numeric(df["nivel_m"], errors="coerce")
    if valores.notna().sum() < int(cfg.get("min_pontos", 8)):
        return df

    instantes = pd.to_datetime(df["datahora"], errors="coerce")
    base = pd.DataFrame({"dh": instantes, "v": valores}).reset_index(drop=True)
    ordem = base.dropna(subset=["dh"]).sort_values("dh").index
    if len(ordem) < int(cfg.get("min_pontos", 8)):
        return df

    serie = pd.Series(base.loc[ordem, "v"].to_numpy(),
                      index=pd.DatetimeIndex(base.loc[ordem, "dh"]))
    janela = f"{int(cfg.get('janela_h', 3))}h"
    mediana = serie.rolling(janela, center=True, min_periods=3).median()
    desvio = (serie - mediana).abs()
    # MAD local: mediana dos próprios desvios na mesma janela.
    mad = desvio.rolling(janela, center=True, min_periods=3).median()
    limite = (float(cfg.get("k_mad", 6.0)) * mad).clip(
        lower=float(cfg.get("desvio_max_m", 0.30)))
    suspeitos = (desvio > limite).fillna(False).to_numpy()
    if not suspeitos.any():
        return df

    limpo = df.copy()
    posicoes = ordem.to_numpy()[suspeitos]
    limpo.loc[limpo.index[posicoes], "nivel_m"] = None
    if cfg.get("avisar", True):
        amostra = serie[suspeitos]
        exemplos = "; ".join(f"{dh:%d/%m %H:%M} {v:.2f} m"
                             for dh, v in list(amostra.items())[:3])
        print(f"[ANA] {rotulo or 'estação'}: {int(suspeitos.sum())} leitura(s) "
              f"descartada(s) por pico irreal ({exemplos}"
              f"{'; ...' if suspeitos.sum() > 3 else ''}).")
    return limpo


def _itens_para_df(items: list[dict], inicio: datetime) -> pd.DataFrame:
    """Normaliza o JSON da ANA em DataFrame com datahora, nivel_m e chuva_mm."""
    registros = []
    for it in items:
        dh = (it.get("Data_Hora_Medicao") or it.get("Data_Atualizacao")
              or it.get("dataHora") or it.get("data"))
        # nível vem em cm na maioria das estações telemétricas
        cota = it.get("Cota_Adotada") or it.get("Cota_Sensor") or it.get("cota")
        chuva = it.get("Chuva_Adotada") or it.get("Chuva_Acumulada") or it.get("chuva")
        try:
            dh = pd.to_datetime(dh)
        except Exception:
            continue
        registros.append({
            "datahora": dh,
            "nivel_m": float(cota) / 100.0 if cota not in (None, "") else None,
            "chuva_mm": float(chuva) if chuva not in (None, "") else None,
        })

    df = pd.DataFrame(registros)
    if df.empty:
        return df
    df = df[df["datahora"] >= inicio].sort_values("datahora").reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────────────────────
# 4) FUNÇÃO PÚBLICA
# ──────────────────────────────────────────────────────────────────────────
def coletar_niveis_rios(dias: int = 7,
                        nomes: list[str] | tuple[str, ...] | None = None
                        ) -> dict[str, pd.DataFrame]:
    """
    Coleta todas as estações, ou somente `nomes` quando informado.

    Retorna: {nome_amigavel: DataFrame[datahora, nivel_m, chuva_mm]}
    """
    vazio = pd.DataFrame(columns=["datahora", "nivel_m", "chuva_mm"])
    resultado = {}
    selecionadas = {
        nome: codigo for nome, codigo in config.ESTACOES_ANA.items()
        if nomes is None or nome in nomes
    }
    for nome, codigo in selecionadas.items():
        print(f"[ANA] Coletando estação {nome} ({codigo})...")
        try:
            resultado[nome] = _consultar_serie(codigo, dias=dias)
        except Exception as exc:
            print(f"[ANA] ERRO na estação {nome}: {exc}")
            resultado[nome] = vazio.copy()

    # ── 2ª rodada: repete só as estações que vieram vazias ───────────────
    pendentes = [n for n, df in resultado.items() if df.empty]
    if pendentes and _esta_indisponivel():
        print(f"[ANA] 2ª rodada CANCELADA: servidor fora do ar "
              f"({_esta_indisponivel()}).")
        pendentes = []
    if pendentes:
        try:
            ler_credenciais()
        except Exception as exc:
            print(f"[ANA] 2ª rodada CANCELADA: credenciais indisponíveis ({exc})")
            pendentes = []
    if pendentes:
        print(f"[ANA] 2ª rodada para {len(pendentes)} estação(ões) vazia(s): "
              f"{', '.join(pendentes)} (aguardando 20s)...")
        time.sleep(20)
        # NÃO força token novo aqui: o manual da ANA alerta que autenticações
        # em alta frequência podem bloquear o IP. O cache cobre 50 min e a
        # renovação automática já acontece em caso de 401.
        for nome in pendentes:
            try:
                df = _consultar_serie(config.ESTACOES_ANA[nome], dias=dias)
                if not df.empty:
                    resultado[nome] = df
                    print(f"[ANA] 2ª rodada recuperou {nome} ✔")
            except Exception as exc:
                print(f"[ANA] 2ª rodada falhou p/ {nome}: {exc}")

    return resultado


def resumo_estacao(df: pd.DataFrame) -> dict:
    """Extrai nível atual e tendência 48h de uma série de estação."""
    if df.empty or df["nivel_m"].dropna().empty:
        return {"nivel_atual_m": None, "tendencia_48h_m": None, "ultima_leitura": None}

    serie = df.dropna(subset=["nivel_m"])
    nivel_atual = serie["nivel_m"].iloc[-1]
    ultima = serie["datahora"].iloc[-1]

    corte = ultima - timedelta(hours=48)
    anteriores = serie[serie["datahora"] <= corte]
    nivel_48h = anteriores["nivel_m"].iloc[-1] if not anteriores.empty else serie["nivel_m"].iloc[0]

    return {
        "nivel_atual_m": round(float(nivel_atual), 2),
        "tendencia_48h_m": round(float(nivel_atual - nivel_48h), 2),
        "ultima_leitura": ultima,
    }


if __name__ == "__main__":
    dados = coletar_niveis_rios(dias=7)
    for nome, df in dados.items():
        print(nome, resumo_estacao(df))
