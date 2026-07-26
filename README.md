# Estágios Operacionais — Plano de Contingência de Porto Alegre

Painel automatizado que cruza dados hidrológicos e meteorológicos e
classifica Porto Alegre em um dos **5 estágios operacionais** do Plano de
Contingência (item 5.1): **NORMALIDADE · MOBILIZAÇÃO · ALERTA · SITUAÇÃO DE
EMERGÊNCIA · CRISE**.

**Realizado por: CISC Porto Alegre — Centro de Informações em Saúde e Clima**

🔗 Painel no ar: `https://ciscpoa.github.io/Estagios_Plano_Contingencia/`

> Ferramenta de apoio à decisão — **não substitui os canais oficiais da
> Defesa Civil**.

---

## O que o painel mostra

- **Banner do estágio atual**, na cor do Plano, com as justificativas
- **Avisos meteorológicos vigentes do INMET** (ou aviso de que não há nenhum)
- **9 cards Nível × Cota de Inundação** (Guaíba em duas réguas, Riacho
  Ipiranga, Sinos, Caí em três estações, Jacuí e Gravataí)
- **Risco por região** — as 17 regiões da cidade, com o status da Defesa
  Civil capturado do mapa do Poaclima
- **Gatilhos de campo confirmados** (SMS/Defesa Civil/CISC)
- **Gráficos**: gauge do estágio, nível do Guaíba com as três cotas, nível
  dos afluentes e precipitação observada × prevista
- **Tema claro/escuro** e botão de **impressão/PDF** (A4 paisagem)

---

## Fontes de dados

| Fonte | O que traz | Como |
|---|---|---|
| **ANA HidroWebService** | nível dos rios (7 estações telemétricas) | API com credenciais |
| **Poaclima** (Defesa Civil de POA) | alertas por região, réguas do Guaíba e do Dilúvio, previsão do tempo (Catavento) | Selenium |
| **INMET** | avisos meteorológicos vigentes; chuva observada da estação automática | API (+ Selenium para os avisos) |
| **Open-Meteo** | chuva observada e prevista — **reserva** | API pública |
| **nivelguaiba.com** | nível do Guaíba — último recurso | Selenium |
| **`gatilhos_manuais.txt`** | eventos confirmados em campo | arquivo no repositório |

**Prioridade da chuva:** observada → INMET (estação) → estações do Poaclima
→ Open-Meteo. Prevista → Poaclima/Catavento → Open-Meteo. O objetivo é usar
as mesmas fontes que a Defesa Civil de POA, evitando divergência.

⚠️ **Cotas e referenciais:** cada régua tem referência de nível própria —
leituras de estações diferentes **não são comparáveis entre si**. Por isso
cada card usa a cota da sua própria régua (ver comentários no `config.py`,
que citam a fonte de cada valor).

---

## Como a classificação funciona

1. **Regras E/OU do Plano** (`logica/estagios.py`): cada estágio tem blocos
   ligados por E, avaliados de CRISE para NORMALIDADE. O primeiro que fecha
   define o estágio.
2. **Regra de piso**: um gatilho confirmado em campo eleva o estágio, no
   mínimo, até a coluna do Plano onde ele aparece (ex.: "bloqueio de vias
   principais" → piso ALERTA; "óbitos" → piso EMERGÊNCIA).
3. **Transparência**: se uma fonte falhar, o painel avisa; e sem dados de
   rios ele mostra **DADOS INSUFICIENTES** em vez de pintar verde.

### Confirmar um gatilho de campo

Edite o **`gatilhos_manuais.txt`** direto pelo GitHub (ícone do lápis) e
troque `nao` por `ok`. O commit dispara o workflow e o painel se atualiza.
Alternativa sem commit: variável `GATILHOS_ATIVOS` (ver abaixo).

---

## Estrutura do projeto

```
config.py                     parâmetros, cotas (com fonte) e limiares
main_pipeline.py              coleta → consolida → exporta → classifica
app.py                        dashboard Dash (interativo)
coleta/
  ana_api.py                  API da ANA (token OAuth, retries, fail-fast)
  open_meteo.py               chuva observada e prevista (reserva)
  inmet_scraper.py            avisos meteorológicos vigentes
  inmet_estacao.py            chuva observada da estação automática
  poaclima_scraper.py         mapa, previsão e estações do Poaclima
  webdriver_utils.py          Chrome headless (Colab, local, container)
  rede.py                     IPv4 forçado e headers de navegador
processamento/consolidacao.py DataFrame único + CSV/Excel
logica/estagios.py            regras E/OU, regra de piso, indicadores
dashboard/
  componentes.py              cards, gauge, gráficos, grid das regiões
  site_estatico.py            gera a página publicada no GitHub Pages
  relatorio_pdf.py            relatório PDF gerado no servidor
.github/workflows/coleta.yml  coleta automática + publicação (gratuito)
```

---

## Como rodar

### GitHub Actions + Pages (produção, gratuito)

Já configurado: o workflow roda a cada 30 min, grava os dados no
repositório e publica a página. Passo a passo em **`HOSPEDAGEM_GRATIS.md`**.

Secrets necessários (`Settings → Secrets and variables → Actions`):

| Secret | Obrigatório | Para quê |
|---|---|---|
| `ANA_IDENTIFICADOR` | sim | API da ANA |
| `ANA_SENHA` | sim | API da ANA |
| `INMET_TOKEN` | não | chuva observada da estação do INMET (o endpoint aberto pode exigir chave) |

Variáveis opcionais: `GATILHOS_ATIVOS`, `USAR_SELENIUM`, `AGENDADOR`,
`INTERVALO_COLETA_MIN`, `DIRETORIO_DADOS`, `SNAPSHOT_URL`.

### Local (VSCode)

```bash
pip install -r requirements.txt
python main_pipeline.py             # coleta e classifica
python -m dashboard.site_estatico   # gera site/index.html
python app.py                       # dashboard interativo em :8050
```

Credenciais: variáveis de ambiente `ANA_IDENTIFICADOR`/`ANA_SENHA` ou o
arquivo `ANA_API_ID_SENHA.txt` (nunca versionado).

### Google Colab

Abra o `Automatizacao_Estagios_Contingencia.ipynb` e rode as células na
ordem (montar Drive → instalar Chrome → conferir credenciais → pipeline →
dashboard inline).

### Servidor (Render, Docker)

`Dockerfile` e `render.yaml` prontos — ver **`README_RENDER.md`**.

---

## Arquivos gerados

Em `arquivos_gerados_2026/`, a cada coleta:
`dados_poa_AAAAMMDD_HHMM.csv`, `.xlsx` (abas Consolidado, Guaiba,
Afluentes, Precipitação) e o relatório PDF quando solicitado. O estado atual
fica em `dados/ultimo_snapshot.json`, que alimenta o painel.

---

## Limitações conhecidas

- O código ANA **85900000** é a estação **Rio Pardo**, não Triunfo; a cota
  de Triunfo (4,67 m) só entra quando o código correto for confirmado no
  HidroWeb.
- Sem cota oficial publicada: Jacuí (na estação lida) e cota de atenção do
  Gravataí.
- O `cron` do GitHub pode atrasar de 5 a 20 min — o painel não serve como
  alarme em tempo real.
- O scraping do Poaclima depende do layout do site; mudanças lá podem exigir
  ajuste nos seletores.
