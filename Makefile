.DEFAULT_GOAL := help
SHELL := /bin/bash
export PYTHONPATH := backend:.

.PHONY: help setup check api up down logs test lint format bench clean

help: ## Показать команды
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Установить зависимости и создать .env
	pip install -e ".[redis,dev]"
	@test -f .env || cp .env.example .env
	@echo "Готово. Дальше: make data && make train"

check: ## Прогнать самопроверку по требованиям ТЗ (нужен запущенный сервис)
	curl -s localhost:8000/api/v1/selfcheck | python -m json.tool

api: ## Запустить сервис локально с автоперезагрузкой
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

up: ## Поднять сервис в Docker (профили: make up PROFILES="--profile redis")
	@test -f .env || cp .env.example .env
	docker compose $(PROFILES) up --build -d
	@echo "Swagger: http://localhost:8000/docs"

down: ## Остановить контейнеры
	docker compose --profile redis --profile db down

logs: ## Логи сервиса
	docker compose logs -f api

test: ## Прогнать тесты
	pytest

lint: ## Проверить стиль
	ruff check backend ml tests

format: ## Отформатировать код
	ruff format backend ml tests
	ruff check --fix backend ml tests

bench: ## Замерить латентность (нужен запущенный сервис)
	python scripts/bench.py

clean: ## Убрать временные файлы
	rm -rf .pytest_cache .ruff_cache catboost_info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
