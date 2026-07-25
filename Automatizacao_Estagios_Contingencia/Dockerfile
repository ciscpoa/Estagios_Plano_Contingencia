# ==========================================================================
# Dockerfile — Estágios Operacionais / CISC Porto Alegre
#
# Imagem para o Render (runtime: docker). O runtime Python nativo do Render
# NÃO tem Chrome e não permite `apt-get`, por isso usamos Docker: aqui o
# Chromium + chromedriver vêm instalados e casados na mesma versão, o que
# faz o Selenium (Poaclima/INMET) funcionar igual ao Colab.
# ==========================================================================
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=America/Sao_Paulo \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_PATH=/usr/bin/chromedriver

# Chromium + driver (versões casadas pelo Debian) e fontes p/ os gráficos
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
        fonts-liberation \
        fonts-dejavu-core \
        ca-certificates \
        tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependências primeiro (aproveita o cache de camadas do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código do projeto
COPY . .

# Pastas de saída (efêmeras sem disco persistente — o agendador recria)
RUN mkdir -p /app/dados /app/arquivos_gerados_2026

# O Render injeta a porta em $PORT (padrão 10000)
ENV PORT=10000
EXPOSE 10000

# 1 worker + threads: garante UM agendador por serviço.
# timeout alto: o botão "Atualizar dados agora" roda o pipeline (~1-2 min).
CMD gunicorn app:server \
    --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 8 \
    --timeout 300 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
