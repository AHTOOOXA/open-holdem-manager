.PHONY: dev backend frontend setup stop

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install

stop:
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:5173 | xargs kill -9 2>/dev/null || true

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev -- --port 5173 --strictPort

dev: stop
	make backend & make frontend
