# 🌊 Automatização dos Estágios Operacionais — Porto Alegre/RS

Sistema automatizado que cruza dados **hidrológicos (ANA)** e **meteorológicos
(Open-Meteo, INMET, Poaclima)** para classificar Porto Alegre em um dos
**5 Estágios Operacionais** do Plano de Contingência (item 5.1 — SMS/PMPA)
e exibir tudo em um **dashboard Dash/Plotly**.

## Estrutura de pastas

```
Automatizacao_Estagios_Contingencia/
├── app.py                      # Dashboard Dash (expõe `server` p/ gunicorn/Render)
├── main_pipeline.py            # Orquestrador: coleta → CSV → classificação
├── config.py                   # Cotas do Guaíba, limiares de chuva, estações, caminhos
├── requirements.txt
├── Procfile / render.yaml      # Deploy Render
├── ANA_API_ID_SENHA.txt        # (VOCÊ cria) credenciais da ANA — fora do git
├── ANA_API_ID_SENHA_EXEMPLO.txt
├── Automatizacao_Estagios_Contingencia.ipynb   # Notebook pronto p/ Colab
├── coleta/
│   ├── ana_api.py              # API HidroWebService da ANA (token OAuth)
│   ├── open_meteo.py           # Previsão/observação de precipitação
│   ├── inmet_scraper.py        # Avisos INMET (API → fallback Selenium)
│   ├── poaclima_scraper.py     # Poaclima + fallback nível do Guaíba
│   └── webdriver_utils.py      # Chrome headless adaptável (local ↔ Colab)
├── processamento/
│   └── consolidacao.py         # DataFrame único + export dados_poa_YYYYMMDD_HHMM.csv
├── logica/
│   └── estagios.py             # Regras E/OU dos 5 estágios + inputs booleanos
├── dashboard/
│   └── componentes.py          # Gauge, banner, gráficos, DataTable
└── dados/                      # CSVs e ultimo_snapshot.json
```

## Como rodar — VSCode local

```bash
pip install -r requirements.txt
# crie ANA_API_ID_SENHA.txt (ID na 1ª linha, senha na 2ª)
python main_pipeline.py            # coleta + CSV + classificação
python app.py                      # dashboard em http://127.0.0.1:8050
```

Sem chrome instalado? `python main_pipeline.py --sem-selenium` roda só as APIs.

## Como rodar — Google Colab

Copie a pasta inteira para
`/content/drive/MyDrive/Colab Notebooks/Automatizacao_Estagios_Contingencia`
e abra o notebook `Automatizacao_Estagios_Contingencia.ipynb`. As células já:
montam o Drive, instalam dependências + chromium-chromedriver, rodam o
pipeline e abrem o dashboard inline.

## Deploy futuro — Render

O `app.py` expõe `server = app.server`; o `Procfile`/`render.yaml` já apontam
para `gunicorn app:server`. Suba o repositório e crie um Web Service Python.
(No Render não há Chrome: agende o pipeline com `--sem-selenium` via Cron Job
ou alimente o `dados/ultimo_snapshot.json` externamente.)

## Lógica dos 5 estágios (resumo)

A função `logica/estagios.classificar_estagio()` avalia de **CRISE → NORMALIDADE**
e retorna o estágio mais grave disparado, com justificativas auditáveis.
Gatilhos matemáticos: cotas do Guaíba (Atenção 2,50 m · Alerta 3,15 m ·
Inundação 3,60 m — ajustáveis no `config.py`), tendência de subida em 48 h,
acumulados de chuva 24 h/72 h/7 d e previsão 48 h. Gatilhos qualitativos
(bloqueio de vias, interrupção de serviços, óbitos, colapso da drenagem…)
entram como **booleanos** no dataclass `InputsInfraestrutura`, marcáveis
direto no dashboard (painel "Gatilhos qualitativos" + botão Reclassificar).

> Ferramenta de apoio à decisão. Não substitui os canais oficiais da
> Defesa Civil e da Prefeitura de Porto Alegre.
