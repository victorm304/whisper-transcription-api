#!/usr/bin/env bash
set -e

echo "Iniciando Redis..."
redis-server --daemonize yes
sleep 2

echo "Iniciando worker RQ..."
rq worker whisper &

echo "Iniciando Gunicorn..."
exec gunicorn -w 1 -k gthread --threads 4 -b 0.0.0.0:50000 app:app
