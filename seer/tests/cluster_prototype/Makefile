# Cluster prototype control. Run `make` for the list of targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE_FILES := -f docker-compose.yml
ifneq ($(strip $(HTTPS_PROXY)),)
PROXY := 1
COMPOSE_FILES += -f docker-compose.proxy.yml
endif
DC := docker compose $(COMPOSE_FILES)
DCL := $(DC) --profile legacy
PSQL := $(DCL) exec -T db psql -U seer -d seer
VIEWER_URL ?= http://localhost:8080
CA_FILE ?= $(or $(SSL_CERT_FILE),/root/.ccr/ca-bundle.crt)
FNS := fn-scrape fn-build
IMAGES := $(FNS)
LEGACY_IMAGES := viewer clusterer
MIGRATE := $(PSQL) -q -v ON_ERROR_STOP=1 -c "set client_min_messages = warning" -f - < db/schema.sql
MIN_SOURCES ?= 2
THRESHOLD ?= 0.92
VIEW ?= top
WAIT_VIEWER := (for _ in $$(seq 1 30); do curl -fsS "$(VIEWER_URL)/healthz" >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1)

# Pipeline runner (stand-in for the scheduler and the S3 event); HOURS and EDITION map to its flags.
PIPELINE := python3 pipeline/run_pipeline.py
S3_DIR := data/s3
PREVIEW_PORT ?= 8090

# Optional per-run overrides for the legacy batch experiment, e.g. `make cluster THRESHOLDS=0.91,0.92`.
JOB_ENV := $(if $(HOURS),-e HOURS=$(HOURS)) $(if $(THRESHOLDS),-e THRESHOLDS=$(THRESHOLDS)) \
	$(if $(WINDOW_HOURS),-e WINDOW_HOURS=$(WINDOW_HOURS)) $(if $(MODEL),-e MODEL=$(MODEL)) \
	$(if $(EDITION),-e EDITION=$(EDITION)) $(if $(MAX_ARTICLES),-e MAX_ARTICLES_PER_SOURCE=$(MAX_ARTICLES))

.PHONY: help all docker certs build build-legacy up up-legacy migrate down restart scrape site preview replay compare raw \
	reset-stories refresh cluster _images open export export-editions ps logs health stats sql psql clear-runs clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'
	@echo "  Variables: HOURS, EDITION, SERVICE, PREVIEW_PORT; legacy: THRESHOLDS, WINDOW_HOURS, MODEL, MAX_ARTICLES, SQL, RUN,"
	@echo "             THRESHOLD, VIEW, MIN_SOURCES, VIEWER_URL"

all: build up refresh site ## Build, start, scrape and build the editions, then print the site path

refresh: docker ## Scrape, then build from the new manifest, per edition (containers up); HOURS, EDITION
	$(PIPELINE) --steps scrape,build $(if $(HOURS),--hours $(HOURS)) $(if $(EDITION),--editions $(EDITION))

scrape: docker ## Scrape to S3 only; HOURS, EDITION
	$(PIPELINE) --steps scrape $(if $(HOURS),--hours $(HOURS)) $(if $(EDITION),--editions $(EDITION))

site: docker ## Build from the latest manifest of each edition, no scraping; print the site path
	$(PIPELINE) --steps build $(if $(EDITION),--editions $(EDITION))
	@echo "Site: $(CURDIR)/$(S3_DIR)/seer-site/index.html (make preview serves it)"

preview: ## Serve the public site from data/s3/seer-site at http://localhost:8090 (PREVIEW_PORT), logging requests to data/logs; Ctrl-C to stop
	@echo "Site: http://localhost:$(PREVIEW_PORT)/index.html (analysis pages under /lab/)"
	@mkdir -p data/logs/cloudfront
	@python3 tools/preview_server.py --port $(PREVIEW_PORT) --directory $(S3_DIR)/seer-site --logs data/logs/cloudfront

replay: docker ## Rebuild editions from scratch: delete their state, apply every manifest in order; EDITION=mk
	$(PIPELINE) --replay $(EDITION)

docker: ## Start the Docker daemon if it isn't running (cloud sandboxes)
	@docker info >/dev/null 2>&1 || { \
		command -v dockerd >/dev/null && [ "$$(id -u)" = 0 ] || { echo "Docker daemon not available" >&2; exit 1; }; \
		(dockerd >"$${TMPDIR:-/tmp}/dockerd.log" 2>&1 &); \
		for _ in $$(seq 1 30); do docker info >/dev/null 2>&1 && exit 0; sleep 1; done; \
		echo "Docker daemon did not start" >&2; exit 1; }

certs:
ifdef PROXY
	@if [ -f "$(CA_FILE)" ]; then cp "$(CA_FILE)" certs/extra-ca.crt; fi
endif

build: docker certs ## Build the images of the two Lambdas
	@$(MAKE) --no-print-directory _images BUILD="$(IMAGES)"

build-legacy: docker certs ## Legacy: build the viewer and clusterer images
	@$(MAKE) --no-print-directory _images BUILD="$(LEGACY_IMAGES)"

# Behind the proxy, Compose's bake builder needs an explicit grant for host-network builds.
_images:
ifdef PROXY
	@bake=$$(mktemp); $(DCL) build --print $(BUILD) >"$$bake" \
		&& docker buildx bake -f "$$bake" --allow=network.host $(BUILD); rc=$$?; rm -f "$$bake"; exit $$rc
else
	$(DCL) build $(BUILD)
endif

up: docker ## Start S3 and the two Lambda containers (no database)
	@mkdir -p $(S3_DIR)
	$(DC) up -d s3 $(FNS)

up-legacy: docker ## Legacy: start Postgres and the viewer, apply the schema
	@mkdir -p $(S3_DIR)
	$(DCL) up -d db viewer
	@$(MIGRATE)
	@$(WAIT_VIEWER) || echo "viewer: not ready after 30 s; see make logs SERVICE=viewer"

migrate: docker ## Legacy: apply db/schema.sql to the running database (idempotent)
	@$(MIGRATE) && echo "schema: up to date"

down: docker ## Stop all containers (all profiles); data is kept
	$(DCL) down

restart: docker ## Restart the Lambda containers
	$(DC) restart $(FNS)

raw: ## List raw/, runs/, state/, archive/ and builds/ objects in data/s3/seer-raw, with sizes
	@d=$(S3_DIR)/seer-raw; [ -d "$$d" ] || { echo "$$d: nothing yet (run make scrape)"; exit 0; }; \
	for p in raw runs state archive builds; do \
		echo "== $$p/"; \
		find "$$d/$$p" -type f 2>/dev/null | sort | while read -r f; do \
			printf "%12d  %s\n" "$$(stat -c %s "$$f")" "$${f#$$d/}"; done; \
		find "$$d/$$p" -type f 2>/dev/null | xargs -r stat -c %s | awk -v p=$$p '{n++; t+=$$1} END {printf "%12d  total %s (%d files)\n", t, p, n}'; \
	done; \
	echo "== all"; du -sh "$$d" | awk '{print "   " $$1 " on disk"}'

compare: docker ## Legacy: compare open stories in S3 (database-free) with Postgres; run up-legacy first
	$(DCL) run --rm -v "$(CURDIR)/tools:/tools:ro" -v "$(CURDIR)/$(S3_DIR):/s3:ro" \
		clusterer python /tools/compare_stories.py

reset-stories: docker ## Legacy: delete all stories in Postgres
	@$(PSQL) -c "delete from stories;"

cluster: docker ## Legacy: batch experiment, re-cluster the whole window at each of THRESHOLDS (cluster_runs)
	$(DCL) run --rm $(JOB_ENV) clusterer

open: ## Legacy: open the viewer in a browser
	@echo "Viewer: $(VIEWER_URL)"
	@if command -v xdg-open >/dev/null; then xdg-open "$(VIEWER_URL)" >/dev/null 2>&1 & \
	elif command -v open >/dev/null; then open "$(VIEWER_URL)"; \
	elif command -v wslview >/dev/null; then wslview "$(VIEWER_URL)"; fi

export: docker ## Legacy: save a run page as static HTML in out/: RUN=<id> (default latest), MIN_SOURCES=2
	@mkdir -p out; run=$(or $(RUN),$$($(PSQL) -tAc "select id from cluster_runs order by id desc limit 1")); \
	curl -fsS "$(VIEWER_URL)/runs/$$run?min_sources=$(MIN_SOURCES)" -o "out/run-$$run.html" \
		&& echo "Saved out/run-$$run.html"

export-editions: docker ## Legacy: save the side-by-side stories page to out/editions.html: VIEW=top|latest
	@mkdir -p out; curl -fsS "$(VIEWER_URL)/editions?view=$(VIEW)&min_sources=$(MIN_SOURCES)" -o out/editions.html \
		&& echo "Saved out/editions.html"

ps: docker ## Show containers (all profiles)
	$(DCL) ps -a

logs: docker ## Follow logs; SERVICE=fn-build|fn-scrape|s3|... for one service
	$(DCL) logs -f --tail=100 $(SERVICE)

health: docker ## Check the Lambda containers; also the viewer and database if up
	@$(DCL) ps --format '{{.Service}}: {{.State}}'
	@$(DCL) ps -q viewer | grep -q . && { $(WAIT_VIEWER) && echo "viewer: ok" || echo "viewer: not responding"; } || true
	@$(DCL) ps -q db | grep -q . && { $(DCL) exec -T db pg_isready -U seer -d seer -q && echo "db: ok" || echo "db: not responding"; } || true

stats: docker ## Legacy: articles per source and the latest cluster runs
	@$(PSQL) -c "select s.domain, count(a.id) as articles, max(a.published_at)::timestamp(0) as newest \
		from sources s left join articles a on a.source_id = s.id group by 1 order by 2 desc;" \
		-c "select id, threshold, article_count as articles, cluster_count as clusters, \
		multi_source_count as multi_source, largest_cluster as largest, created_at::timestamp(0) \
		from cluster_runs order by id desc limit 10;"

sql: docker ## Legacy: run one query: make sql SQL="select count(*) from articles"
	@$(PSQL) -c "$(SQL)"

psql: docker ## Legacy: open an interactive psql shell
	$(DCL) exec db psql -U seer -d seer

clear-runs: docker ## Legacy: delete all cluster runs; articles and embeddings stay
	@$(PSQL) -c "delete from cluster_runs;"

clean: docker ## Stop everything and delete all data, including the model cache and data/s3
	$(DCL) down -v
	@find $(S3_DIR) -mindepth 1 -delete 2>/dev/null || true
	rm -f certs/extra-ca.crt
