# Makefile — Ultron Voice

.PHONY: help install lint test check health clean

help: ## Mostra esta ajuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-22s %s\n", $$1, $$2}'

install: ## Cria ambiente virtual com uv e instala o projeto
	uv venv .venv
	uv pip install -e ".[dev]"

lint: ## Verifica estilo (ruff/black se disponíveis)
	ruff check backend mcp_server.py cli tests || true

test: ## Rodas os testes focados (sem cobrir tudo)
	uv run pytest tests -q --ignore=tests/e2e --ignore=tests/perf

check: lint test ## Lint + teste

health: ## Verifica pip, ffmpeg e engines disponiveis
	@command -v ffmpeg >/dev/null && echo "ffmpeg: OK" || echo "ffmpeg: MISSING"
	@command -v uv >/dev/null && echo "uv: OK" || echo "uv: MISSING"
	@command -v python3 >/dev/null && echo "python3: OK" || echo "python3: MISSING"

clean: ## Remove artefatos temporários
	rm -rf .pytest_cache .ruff_cache *.egg-info build dist
