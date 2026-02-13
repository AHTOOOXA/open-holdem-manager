.PHONY: dev backend frontend setup stop electron-dev electron-build

setup:
	cd backend && pip install -r requirements.txt
	cd frontend && npm install
	npm install

stop:
	@lsof -ti:8000 | xargs kill -9 2>/dev/null || true
	@lsof -ti:5173 | xargs kill -9 2>/dev/null || true

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev -- --port 5173 --strictPort

dev: stop
	make backend & make frontend

# Electron development: start backend + frontend, then launch Electron
electron-dev: stop
	make backend & make frontend & sleep 3 && npm run electron:dev

# Build distributable Electron app (requires PyInstaller: pip install pyinstaller)
electron-build:
	cd frontend && npm run build
	cd backend && pyinstaller --name ohm-backend --onedir --noconfirm --clean \
		--collect-submodules uvicorn --collect-submodules fastapi \
		--collect-submodules starlette --collect-submodules pydantic \
		--collect-submodules duckdb --hidden-import multipart \
		run_server.py
	npx electron-builder
