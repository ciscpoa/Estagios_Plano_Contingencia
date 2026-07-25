# Usado apenas por plataformas estilo Heroku. No Render, quem manda é o
# CMD do Dockerfile (runtime: docker).
web: gunicorn app:server --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 300
