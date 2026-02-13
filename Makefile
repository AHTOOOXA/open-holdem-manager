.PHONY: dev backend frontend setup stop electron-dev electron-build release

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
	cd frontend && ELECTRON=1 npm run build
	cd backend && pyinstaller --name ohm-backend --onedir --noconfirm --clean \
		--collect-submodules uvicorn --collect-submodules fastapi \
		--collect-submodules starlette --collect-submodules pydantic \
		--collect-submodules duckdb --hidden-import multipart \
		run_server.py
	npx electron-builder

# Release: bump version, commit, tag, push → CI builds & publishes
# Usage: make release v=0.0.3
release:
ifndef v
	$(error Usage: make release v=0.0.3)
endif
	@echo "Releasing v$(v)..."
	npm version $(v) --no-git-tag-version
	git add package.json package-lock.json
	git commit -m "v$(v)"
	git tag "v$(v)"
	git push origin main "v$(v)"
	@echo "Release v$(v) triggered. Watch: https://github.com/AHTOOOXA/open-holdem-manager/actions"
