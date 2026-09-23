# Зависимости ставятся отдельным слоем до копирования исходников:
# правка кода пересобирает образ за секунды, а не за минуты.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/srv/backend:/srv

WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY backend ./backend
COPY ml ./ml

# Непривилегированный пользователь: root в контейнере не нужен даже на хакатоне.
RUN useradd --create-home --uid 1000 app && chown -R app:app /srv
USER app

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
