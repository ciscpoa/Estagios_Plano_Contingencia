# Estágios Operacionais — Plano de Contingência para Chuvas Intensas

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

- **Escala dos 5 estágios** em chevrons, com o degrau atual destacado
- **Banner do estágio**, na cor do Plano, com os blocos da regra E/OU e o
  motivo de cada bloco discriminado por tópicos
- **Avisos meteorológicos vigentes do INMET**, como complemento à análise
- **12 cards Nível × Cota de Inundação**, um por régua monitorada
- **Risco por região** — as 17 regiões da cidade, com o status da Defesa
  Civil capturado do mapa do Poaclima
- **Gráficos**: nível do Guaíba com as três cotas, afluentes (uma linha por
  rio) e chuva observada × prevista
- **Previsão de 5 dias** do Poaclima/Catavento
- **Tema claro/escuro** e botão de **impressão/PDF** em A4 paisagem,
  desenhado para sair legível também em preto e branco

---

## Estações monitoradas

Cada card usa a cota da **sua própria régua**. Referenciais de nível são
locais e arbitrários: **leituras de estações diferentes não se comparam**.

| Corpo d'água | Estação | Código | Cota de inundação | Fonte da cota |
|---|---|---|---|---|
| Guaíba | Cais Mauá | ANA 87450004 | 3,00 m | Poaclima/SEMA-RS |
| Guaíba | Usina do Gasômetro | Poaclima | 2,60 m | Poaclima/DC-POA |
| Ipiranga | Arroio Dilúvio | Poaclima | 4,00 m | Poaclima/DC-POA |
| Rio dos Sinos | São Leopoldo | ANA 87382000 | 4,50 m | DC de São Leopoldo |
| Rio Caí | Barca do Caí | ANA 87170000 | 10,50 m | SGB — SAH Rio Caí |
| Rio Caí | Passo Montenegro | ANA 87270000 | 6,00 m | SGB — SAH Rio Caí |
| Rio Caí | Nova Palmira | ANA 87160000 | 4,70 m | SGB — SAH Rio Caí |
| Rio Jacuí | Triunfo | ANA 87010000 | 4,67 m | DC de Triunfo |
| Rio Jacuí | Passo São Lourenço | ANA 85642000 | 9,00 m | DC / SGB |
| Rio Taquari | Muçum | ANA 86510000 | 18,00 m | SGB — SAH Rio Taquari |
| Rio Taquari | Taquari | ANA 86950000 | 8,50 m | SGB — SAH Rio Taquari |
| Rio Gravataí | Passo das Canoas | ANA 87399000 | 4,75 m | ANA / Defesa Civil |

**No gráfico de afluentes entra só uma linha por rio** — a régua mais
próxima do Guaíba (Gravataí, Sinos/São Leopoldo, Caí/Montenegro,
Jacuí/Triunfo e Taquari/Taquari). As demais continuam coletadas e nos cards;
sete curvas disputando a mesma área não se leem.

### Telemétrica ou convencional?

Nem toda estação do HidroWebService transmite em tempo real, e o nome não
diz qual é qual. O teste que usamos, direto na API:

- **telemétrica** — 15 a 45 min entre leituras, `Cota_Sensor` preenchida;
- **convencional** — 720 a 840 min (leituras de régua às 07h e 17h),
  `Cota_Sensor` sempre vazia, publicação com cerca de um dia de atraso.

Foi assim que a 85900000 (Rio Pardo) e a 87020000 (São Jerônimo) foram
identificadas como convencionais e substituídas por telemétricas no Jacuí.
O inventário completo do estado sai em
`EstacoesTelemetricas/HidroInventarioEstacoes/v1?Unidade Federativa=RS`.

---

## Fontes de dados

| Fonte | O que traz | Como |
|---|---|---|
| **ANA HidroWebService** | nível dos rios (10 estações) | API com credenciais |
| **Poaclima** (Defesa Civil de POA) | alertas por região, réguas do Guaíba e do Dilúvio, previsão do tempo (Catavento) | Selenium |
| **INMET** | avisos meteorológicos vigentes; chuva observada da estação automática | API (+ Selenium para os avisos) |
| **Open-Meteo** | chuva observada e prevista — **reserva** | API pública |
| **nivelguaiba.com** | nível do Guaíba — último recurso | Selenium |
| **`gatilhos_manuais.txt`** | eventos confirmados em campo | arquivo no repositório |

**Prioridade da chuva:** observada → INMET (estação) → estações do Poaclima
→ Open-Meteo. Prevista → Poaclima/Catavento → Open-Meteo. O objetivo é usar
as mesmas fontes que a Defesa Civil de POA, evitando divergência.

---

## Como a classificação funciona

1. **Regras E/OU do Plano** (`logica/estagios.py`): cada estágio tem blocos
   ligados por E, avaliados de CRISE para NORMALIDADE. O primeiro que fecha
   define o estágio.
2. **Regra de piso**: um gatilho confirmado em campo eleva o estágio, no
   mínimo, até a coluna do Plano onde ele aparece (ex.: "bloqueio de vias
   principais" → piso ALERTA; "óbitos" → piso EMERGÊNCIA).
3. **Cotas com fallback**: nem toda régua publica as três cotas. Quando não
   há cota de atenção, vale a menor cota publicada daquela estação, e o
   painel **diz qual cota está sendo considerada** ("Gravataí 4,68 m ≥
   alerta 4,25 m"). Um rio acima da cota de inundação está, por definição,
   acima da de atenção.
4. **Transparência**: se uma fonte falhar, o painel avisa; e sem dados de
   rios ele mostra **DADOS INSUFICIENTES** em vez de pintar verde.

### Guarda de publicação

Coleta ruim não sobrescreve painel bom (`processamento/publicacao.py`).
Quando a ANA não responde, os níveis chegam vazios e a classificação cairia
para NORMALIDADE com um "Última atualização" recém-carimbado — falha de
coleta disfarçada de boa notícia. Nesse caso **nada é gravado**: estágio,
cards, gráficos e horário ficam como estavam.

Duas exceções, ambas de segurança:

- **agravamento** — se o estágio *sobe* mesmo sem a ANA (chuva extrema,
  aviso vermelho, gatilho de campo), publica: congelar esconderia a piora;
- **validade** — passadas 6 h, dado velho vira ilusão; publica o incompleto,
  que já sai com o aviso de fontes fora.

### Confirmar um gatilho de campo

Edite o **`gatilhos_manuais.txt`** direto pelo GitHub (ícone do lápis) e
troque `nao` por `ok`. O commit dispara o workflow e o painel se atualiza.
Alternativa sem commit: variável `GATILHOS_ATIVOS`.

---

## Impressão e PDF

O botão 🖨 usa o diálogo do navegador; o layout de impressão está no bloco
`@media print` do `dashboard/site_estatico.py`. A folha é A4 paisagem e o
princípio é que **nada dependa só da cor**, porque o documento circula
fotocopiado:

- selo textual em cada card (NORMAL · ATENÇÃO · ALERTA · INUNDAÇÃO);
- hachura na barra e nas células de risco, mais densa conforme a gravidade;
- marca **ETAPA ATUAL** no degrau vigente da escala;
- traço próprio para cada rio nos gráficos e espessura crescente nas cotas;
- página final **"Como ler este documento"**, que só existe no papel.

No diálogo do Chrome, desmarque "Cabeçalhos e rodapés" para tirar a URL e a
data do navegador.

---

## Estrutura do projeto

```
config.py                     parâmetros, cotas (com fonte) e limiares
main_pipeline.py              coleta → consolida → exporta → classifica
app.py                        dashboard Dash (não usado em produção)
gatilhos_manuais.txt          gatilhos de campo confirmados
coleta/
  ana_api.py                  API da ANA (token OAuth, retries, fail-fast)
  chuva_observada.py          chuva medida: INMET → Poaclima → ANA
  defesacivil_avisos.py       avisos da Defesa Civil de POA
  inmet_scraper.py            avisos meteorológicos vigentes
  open_meteo.py               chuva observada e prevista (reserva)
  poaclima_scraper.py         mapa, previsão e estações do Poaclima
  rede.py                     IPv4 forçado e headers de navegador
  webdriver_utils.py          Chrome headless (Colab, local, container)
processamento/
  consolidacao.py             DataFrame único + exportações
  alinhamento_afluentes.py    séries dos afluentes e histórico persistido
  publicacao.py               guarda de publicação (congela coleta ruim)
logica/estagios.py            regras E/OU, regra de piso, indicadores
dashboard/
  componentes.py              cards, gauge, gráficos, grid das regiões
  site_estatico.py            gera a página publicada no GitHub Pages
  relatorio_pdf.py            relatório PDF gerado no servidor
dados/
  ultimo_snapshot.json        estado atual que alimenta o painel
  historico_niveis_ana.csv    série longa das estações da ANA
.github/workflows/
  coleta.yml                  coleta automática + publicação
  gatilho-externo.yml         disparo externo (cron-job.org)
  previa.yml                  prévia de alterações
```

---

## Como rodar

### GitHub Actions + Pages (produção, gratuito)

O workflow roda três vezes por hora (minutos 4, 24 e 44), grava os dados no
repositório e publica a página. Há ainda o `gatilho-externo.yml`, chamável
de fora (cron-job.org) com guarda de 25 min contra coleta redundante.

Secrets (`Settings → Secrets and variables → Actions`):

| Secret | Obrigatório | Para quê |
|---|---|---|
| `ANA_IDENTIFICADOR` | sim | API da ANA |
| `ANA_SENHA` | sim | API da ANA |
| `INMET_TOKEN` | não | chuva observada da estação do INMET |

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

---

## Limitações conhecidas

- **Cotas incompletas**: Jacuí (Triunfo e Cachoeira do Sul) e Gravataí só
  têm parte das cotas publicadas em fonte oficial. O painel usa a menor cota
  disponível e informa qual é — não inventamos valores.
- **Referenciais locais**: as réguas do Cais Mauá e da Usina do Gasômetro
  medem o mesmo Guaíba e mostram números diferentes. É esperado.
- **Latência do agendador**: o `cron` do GitHub pode atrasar de 5 a 20 min —
  o painel não serve como alarme em tempo real.
- **Scraping do Poaclima** depende do layout do site; mudanças lá exigem
  ajuste nos seletores.
- **Previsão de nível** ficou fora do painel: não é atribuição do CISC. As
  curvas terminam na última leitura observada, marcada pela linha "Agora".
