# Deploy no Render (via GitHub) — CISC Porto Alegre

Guia curto: **subir a pasta no GitHub → apontar o Render para o repositório →
preencher 2 variáveis → pronto.** O painel fica no ar em um endereço
`https://estagios-poa-cisc.onrender.com` e se atualiza sozinho.

---

## 1. Subir para o GitHub

```bash
cd Automatizacao_Estagios_Contingencia
git init
git add .
git commit -m "Painel de Estágios Operacionais - CISC POA"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

> **Confira antes do push:** o `.gitignore` já bloqueia o
> `ANA_API_ID_SENHA.txt`. Rode `git status` e certifique-se de que ele
> **não** aparece na lista de arquivos a enviar. As credenciais vão para o
> Render como variáveis de ambiente, nunca para o repositório.

---

## 2. Criar o serviço no Render

1. Acesse [dashboard.render.com](https://dashboard.render.com) → **New +** →
   **Blueprint**.
2. Conecte a conta do GitHub e selecione o repositório.
3. O Render lê o `render.yaml` sozinho e propõe o serviço
   `estagios-poa-cisc`. Clique em **Apply**.
4. Na tela do serviço, vá em **Environment** e preencha:
   - `ANA_IDENTIFICADOR` → seu identificador da ANA
   - `ANA_SENHA` → sua senha da ANA
5. **Save, rebuild and deploy**.

A primeira build demora ~5–8 minutos (a imagem instala o Chromium). Nos
deploys seguintes, o cache do Docker deixa tudo bem mais rápido.

> Alternativa sem Blueprint: **New +** → **Web Service** → selecione o
> repositório → em *Language/Runtime* escolha **Docker** → adicione as
> variáveis da seção 4 manualmente.

---

## 3. Como saber se funcionou

| Verificação | O que esperar |
|---|---|
| `https://SEU-APP.onrender.com/health` | `{"status": "ok", "snapshot": true}` |
| Logs do Render | `[AGENDADOR] Ativo`, depois `[ANA] Coletando estação...` |
| Página inicial | Banner do estágio + cards + gráficos |

No primeiro minuto após o deploy o painel pode dizer *"Nenhum snapshot
encontrado"* — é o agendador ainda coletando. Recarregue em ~1 minuto.

---

## 4. Variáveis de ambiente

| Variável | Padrão | Para que serve |
|---|---|---|
| `ANA_IDENTIFICADOR` | — | Credencial da API da ANA (**obrigatória**) |
| `ANA_SENHA` | — | Credencial da API da ANA (**obrigatória**) |
| `INTERVALO_COLETA_MIN` | `30` | Minutos entre coletas automáticas |
| `USAR_SELENIUM` | `1` | `0` desliga Poaclima/INMET via navegador |
| `AGENDADOR` | `1` | `0` desliga a coleta automática |
| `GATILHOS_ATIVOS` | vazio | Gatilhos confirmados, separados por vírgula |
| `DIRETORIO_DADOS` | pasta do app | Use com disco persistente (ex.: `/var/data`) |
| `TZ` | `America/Sao_Paulo` | Fuso dos horários exibidos |

### Confirmar um gatilho de campo sem `git push`

No Render: **Environment** → `GATILHOS_ATIVOS` →
`bloqueio_vias_principais,obitos_pelo_evento` → **Save, rebuild and
deploy**. Vale a mesma regra de piso do Plano (o estágio sobe até a coluna
correspondente). Os nomes válidos estão em `gatilhos_manuais.txt`.

---

## 5. O Selenium vai funcionar? (expectativa honesta)

| Fonte | Como é coletada | Expectativa no Render |
|---|---|---|
| **ANA** (níveis dos rios) | API HTTPS | Alta — só depende das credenciais |
| **Open-Meteo** (chuva) | API HTTPS pública | Alta |
| **INMET** (avisos) | API + Selenium | Média — a API já bloqueia por User-Agent e pode bloquear mais um IP de datacenter |
| **Poaclima** (níveis + alertas por região) | Selenium no mapa | Média-alta — o Chromium sobe sem problema; o risco é memória e bloqueio de IP |

**O que está resolvido:** o Chromium vem instalado e casado com o driver na
imagem, com `--no-sandbox` e `--disable-dev-shm-usage` (sem isso ele nem
inicia como root em container), além de flags de baixo consumo.

**O que só o primeiro deploy dirá:**

1. **Memória.** Chromium abrindo um mapa Leaflet consome ~300–500 MB. Nos
   planos *free* e *starter* (512 MB), a coleta do Poaclima pode ser morta
   por falta de memória. Por isso o `render.yaml` vem com `standard` (2 GB).
2. **Bloqueio de IP.** O Render roda nos EUA. Sites públicos brasileiros às
   vezes tratam IPs de datacenter estrangeiro de forma diferente (o 403 do
   INMET que já enfrentamos é dessa família). Não dá para prever sem testar.

**Como saber em 1 minuto, sem adivinhação:** depois do deploy, abra
`https://SEU-APP.onrender.com/diagnostico`. Ele responde algo assim:

```json
{"ultima_coleta": "25/07/2026 13:10", "estagio": "MOBILIZAÇÃO",
 "fontes": {"ANA": true, "Open-Meteo": true, "INMET": false, "Poaclima": true},
 "alertas_regionais": 3}
```

`"Poaclima": true` com `alertas_regionais` maior que zero = Selenium
funcionando de verdade no Render.

**Se o Poaclima falhar, o painel avisa.** Aparece uma tarja de atenção
dizendo quais fontes não foram consultadas e que a classificação pode estar
subestimada — uma falha silenciosa seria perigosa num painel público, já que
sem o Poaclima os alertas da Defesa Civil não entram na regra.

**Plano B, em ordem de esforço:**

1. `SELENIUM_SEM_IMAGENS=1` — Chromium sem baixar os tiles do mapa (bem mais
   leve; os marcadores continuam clicáveis).
2. Subir para `standard` (2 GB), se o problema for memória.
3. `USAR_SELENIUM=0` — o painel roda com ANA + Open-Meteo (rios e chuva
   continuam corretos; perdem-se os alertas por região e o INMET).
4. Manter a coleta no Colab (onde já funciona) e usar o Render só para
   exibir: basta o Colab gravar o `ultimo_snapshot.json` em um local que o
   serviço leia (ex.: disco persistente ou um bucket). Posso montar isso se
   for o caminho escolhido.

---

## 6. Coisas boas de saber

**Plano.** O `render.yaml` vem com `plan: standard` (2 GB) por causa do
Chromium. *Free* e *starter* têm 512 MB — funcionam bem com
`USAR_SELENIUM=0`. O plano free ainda hiberna após ~15 min sem acesso: a
primeira visita demora a abrir e o agendador fica parado enquanto dorme.

**Arquivos gerados.** Sem disco persistente, os CSV/Excel/PDF vivem dentro
do container e somem a cada deploy — o painel não depende deles (o
agendador recria o snapshot no boot). Para manter histórico, descomente o
bloco `disk` no `render.yaml` e a variável `DIRETORIO_DADOS` (planos pagos).

**Botão "Atualizar dados agora".** Roda o pipeline na hora (~1–2 min). O
`timeout` do gunicorn já está em 300s para isso. No uso normal, o agendador
resolve sozinho.

**Um worker.** O `CMD` usa `--workers 1 --threads 8` de propósito: garante
um único agendador por serviço. Se aumentar os workers, cada um vai coletar
por conta própria.

**Colab e local continuam iguais.** Nada do que foi adicionado muda o
comportamento no notebook ou no `python app.py` — o agendador só liga
sozinho quando detecta o Render (ou com `AGENDADOR=1`).
