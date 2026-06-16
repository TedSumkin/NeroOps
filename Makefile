.PHONY: install dev build run test lint backup install-service uninstall-service docker

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e ".[dev]"
	cd frontend && npm install

dev:
	./scripts/run-dev.sh

build:
	cd frontend && npm run build

run: build
	.venv/bin/uvicorn neroops.main:app --app-dir backend --host 127.0.0.1 --port 8000

test:
	.venv/bin/pytest
	cd frontend && npm test
	cd frontend && npm run test:e2e

lint:
	.venv/bin/ruff check backend tests migrations scripts
	cd frontend && npm run build

backup:
	.venv/bin/python scripts/backup.py

install-service: build
	.venv/bin/python scripts/install_launch_agents.py

uninstall-service:
	.venv/bin/python scripts/install_launch_agents.py --uninstall

docker:
	docker-compose up --build
