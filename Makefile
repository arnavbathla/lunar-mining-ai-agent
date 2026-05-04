.PHONY: install dev test seed api web

install:
	cd apps/api && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
	cd apps/web && npm install

api:
	cd apps/api && . .venv/bin/activate && uvicorn main:app --reload --port 8000

web:
	cd apps/web && npm run dev

dev:
	@echo "Run 'make api' and 'make web' in two terminals, or use 'docker compose up --build'."

test:
	cd apps/api && . .venv/bin/activate && pytest -q

seed:
	curl -X POST http://localhost:8000/demo/seed | head -c 2000
