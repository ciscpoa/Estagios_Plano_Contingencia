# Como colocar o painel no ar de graça

Resumo: **o caminho recomendado é 100% gratuito e não hiberna** — o GitHub
faz a coleta (com Chrome de verdade) e publica a página. Só precisa de uma
conta no GitHub.

## Comparação rápida

| Opção | Custo | Selenium (Poaclima/INMET) | Hiberna? |
|---|---|---|---|
| **GitHub Actions + Pages** (recomendado) | **grátis** | ✅ runner tem Chrome e 16 GB | ❌ nunca |
| Render Free só exibindo | grátis | ❌ (coleta vem do GitHub) | após 15 min parado |
| Render Standard | US$ 25/mês | ✅ | ❌ |
| Hugging Face Spaces | grátis*, veja nota | ✅ 16 GB de RAM | após 48 h parado |

\* Spaces com Docker passaram a exigir plano pago para criação em contas
novas. Se a sua conta permitir, é uma ótima opção; se aparecer "Docker =
Paid", siga pelo GitHub.

---

# Opção 1 — GitHub Actions + GitHub Pages (recomendada)

O GitHub roda a coleta a cada 30 minutos num computador dele (com Chrome
instalado, 16 GB de RAM — folgado para o Poaclima), grava os dados no
repositório e publica a página. Repositório **público** tem minutos
ilimitados.

### Passo a passo

**1. Suba a pasta no GitHub** (veja `README_RENDER.md`, seção 1). Deixe o
repositório **Público** para ter minutos ilimitados.

**2. Cadastre as credenciais da ANA**
`Settings` → `Secrets and variables` → `Actions` → `New repository secret`:
- `ANA_IDENTIFICADOR`
- `ANA_SENHA`

**3. Ligue o Pages**
`Settings` → `Pages` → em *Source*, escolha **GitHub Actions**.

**4. Rode a primeira vez**
Aba `Actions` → workflow *"Coleta e publicação do painel"* → **Run
workflow**. Leva ~3 minutos.

**5. Pronto**
O painel fica em `https://SEU_USUARIO.github.io/SEU_REPOSITORIO/`.
A partir daí ele se atualiza sozinho a cada 30 minutos.

### O que você ganha

- Página com banner do estágio, cards Nível×Cota, grid das 17 regiões,
  gauge e os gráficos Plotly **interativos** (com os tooltips bonitos),
  tema claro/escuro e botão de impressão/PDF.
- Histórico versionado: cada coleta commita o `ultimo_snapshot.json` e as
  planilhas em `arquivos_gerados_2026/`.
- **Gatilhos de campo pelo navegador:** edite o `gatilhos_manuais.txt` direto
  no GitHub (ícone do lápis → troque `nao` por `ok` → *Commit*). O workflow
  detecta a mudança e republica o painel na hora.

### Ajustes úteis

- **Frequência:** no arquivo `.github/workflows/coleta.yml`, linha do `cron`.
  `"0,30 * * * *"` = a cada 30 min; `"0 * * * *"` = de hora em hora (use esta
  se o repositório for privado, para caber nos 2.000 min/mês gratuitos).
- **Repositório privado:** funciona igual, mas o GitHub Pages de repositório
  privado exige plano pago. Nesse caso, use a Opção 2 para exibir.

### Limitações honestas

- O `cron` do GitHub pode atrasar de 5 a 20 minutos em horários de pico —
  irrelevante para um painel que se atualiza a cada 30 min, mas não serve
  para alarme em tempo real.
- Workflows agendados são desativados após 60 dias **sem nenhuma atividade**
  no repositório. Como cada coleta faz um commit, isso não deve acontecer.
- A página é estática: sem o botão "Atualizar dados agora" e sem o PDF
  gerado no servidor (mas o botão de impressão salva em PDF pelo navegador).

---

# Opção 2 — Render Free só para exibir (Dash interativo)

Se quiser o dashboard Dash original (com os botões), rode-o no plano **Free**
do Render **sem coletar nada** — quem coleta é o GitHub Actions da Opção 1.
Sem Chromium, 512 MB sobra.

No Render, crie o Web Service normalmente (Docker) e defina:

| Variável | Valor |
|---|---|
| `USAR_SELENIUM` | `0` |
| `AGENDADOR` | `0` |
| `SNAPSHOT_URL` | `https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/dados/ultimo_snapshot.json` |

O painel passa a ler o snapshot publicado pelo GitHub. Lembre que o plano
free hiberna após 15 minutos sem visitas (a primeira visita depois disso
demora ~50 s para abrir).

---

# Opção 3 — Hugging Face Spaces

Se a sua conta permitir criar um **Docker Space** gratuito (16 GB de RAM),
o projeto roda inteiro lá, Selenium incluído:

1. huggingface.co → **New Space** → SDK **Docker** → Blank.
2. Envie os arquivos do projeto.
3. No `Dockerfile`, troque a última linha `ENV PORT=10000` por
   `ENV PORT=7860` (o Spaces exige a porta 7860).
4. Em `Settings` → `Variables and secrets`, cadastre `ANA_IDENTIFICADOR` e
   `ANA_SENHA`.

O Space hiberna após 48 h sem visitas e acorda sozinho quando alguém entra.

---

## Recomendação final

Comece pela **Opção 1**. Ela é gratuita de verdade, aguenta o Selenium sem
sustos de memória, não hiberna e ainda te dá histórico versionado dos dados.
Se mais adiante o CISC quiser o painel interativo com um endereço próprio,
a Opção 2 se soma sem retrabalho — as duas leem exatamente o mesmo snapshot.
