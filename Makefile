# Prüfen vor dem Ausliefern:  make check   (Backend + Frontend-Unit-Tests + Build + Rauchtest gegen :8050)
.PHONY: check test build smoke deploy docker
test:
	MAP_DB=/tmp/fgmap-test.db .venv/bin/python -m pytest tests -q
	cd frontend && pnpm test
build:
	cd frontend && pnpm run check && pnpm run build
smoke:
	node frontend/tests/smoke.mjs $(URL)
check: test build smoke
deploy: check
	systemctl --user restart satisfactory-map
docker:
	docker build -t satisfactory-map .
