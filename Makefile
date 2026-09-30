# Prüfen vor dem Ausliefern:  make check   (Backend + Frontend-Unit-Tests + Build + Rauchtest gegen :8050)
.PHONY: check test build smoke deploy docker wiki
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
wiki:   # docs/wiki → GitHub-Wiki (das Wiki muss einmal über die Weboberfläche angelegt worden sein)
	rm -rf /tmp/fgmap-wiki && git clone -q https://github.com/Fade97/satisfactory-logistikkarte.wiki.git /tmp/fgmap-wiki
	cd /tmp/fgmap-wiki && git rm -rqf --ignore-unmatch . && cp $(CURDIR)/docs/wiki/*.md . && rm -f README.md \
	  && git add -A && (git -c user.name=Fade97 -c user.email=24256873+Fade97@users.noreply.github.com commit -qm "Wiki aus docs/wiki" || true) && git push -q
