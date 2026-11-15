# Cluster prototype control. Run `make` for the list of targets.
SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE_FILES := -f docker-compose.yml
ifneq ($(strip $(HTTPS_PROXY)),)
PROXY := 1
COMPOSE_FILES += -f docker-compose.proxy.yml
endif
DC := docker compose $(COMPOSE_FILES)
PSQL := $(DC) exec -T db psql -U seer -d seer
VIEWER_URL ?= http://localhost:8080
CA_FILE ?= $(or $(SSL_CERT_FILE),/root/.ccr/ca-bundle.crt)
FNS := fn-scrape fn-ingest fn-stories fn-export
IMAGES := viewer clusterer $(FNS)
MIGRATE := $(PSQL) -q -v ON_ERROR_STOP=1 -c "set client_min_messages = warning" -f - < db/schema.sql
MIN_SOURCES ?= 2
THRESHOLD ?= 0.92
VIEW ?= top
WAIT_VIEWER := (for _ in $$(seq 1 30); do curl -fsS "$(VIEWER_URL)/healthz" >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1)

# Pipeline runner (stand-in for Step Functions); HOURS and EDITION map to its flags.
PIPELINE := python3 pipeline/run_pipeline.py $(if $(HOURS),--hours $(HOURS)) $(if $(EDITION),--editions $(EDITION))
S3_DIR := data/s3

# Optional per-run overrides for the batch experiment, e.g. `make cluster THRESHOLDS=0.91,0.92`.
JOB_ENV := $(if $(HOURS),-e HOURS=$(HOURS)) $(if $(THRESHOLDS),-e THRESHOLDS=$(THRESHOLDS)) \
	$(if $(WINDOW_HOURS),-e WINDOW_HOURS=$(WINDOW_HOURS)) $(if $(MODEL),-e MODEL=$(MODEL)) \
	$(if $(EDITION),-e EDITION=$(EDITION)) $(if $(MAX_ARTICLES),-e MAX_ARTICLES_PER_SOURCE=$(MAX_ARTICLES))

.PHONY: help all docker certs build up migrate down restart scrape cluster stories site raw reset-stories refresh open \
	export export-editions ps \
	logs health stats sql psql clear-runs clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'
	@echo "  Variables: HOURS, THRESHOLDS, WINDOW_HOURS, MODEL, EDITION, MAX_ARTICLES, SERVICE, SQL, RUN,"
	@echo "             THRESHOLD, VIEW, MIN_SOURCES, VIEWER_URL"

all: build up refresh open ## Build, start, run the whole pipeline, then open the viewer

refresh: docker ## Run all four steps: scrape, ingest, stories, export (containers already up)
	$(PIPELINE) --steps scrape,ingest,stories,export

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

build: docker certs ## Build all images
ifdef PROXY
	@# Compose's bake builder needs an explicit grant for host-network builds.
	@bake=$$(mktemp); $(DC) build --print $(IMAGES) >"$$bake" \
		&& docker buildx bake -f "$$bake" --allow=network.host $(IMAGES); rc=$$?; rm -f "$$bake"; exit $$rc
else
	$(DC) build $(IMAGES)
endif

up: docker ## Start the database, S3, the four Lambda containers and the viewer
	@mkdir -p $(S3_DIR)
	$(DC) up -d db s3 $(FNS) viewer
	@$(MIGRATE)
	@$(WAIT_VIEWER) || echo "viewer: not ready after 30 s; see make logs SERVICE=viewer"

migrate: docker ## Apply db/schema.sql to the running database (idempotent)
	@$(MIGRATE) && echo "schema: up to date"

down: docker ## Stop all containers; data is kept
	$(DC) --profile jobs down

restart: docker ## Restart the viewer
	$(DC) restart viewer

scrape: docker ## Scrape to S3 and ingest into Postgres (HOURS, EDITION)
	$(PIPELINE) --steps scrape,ingest

stories: docker ## Embed new articles and add them to stable stories (incremental; new articles only)
	$(PIPELINE) --steps stories

site: docker ## Export the static site to S3, then print the path of its index.html
	$(PIPELINE) --steps export
	@echo "Site: $(CURDIR)/$(S3_DIR)/seer-site/index.html"

raw: ## List raw objects, manifests and state in data/s3/seer-raw, with sizes
	@d=$(S3_DIR)/seer-raw; [ -d "$$d" ] || { echo "$$d: nothing yet (run make scrape)"; exit 0; }; \
	for p in raw runs state; do \
		echo "== $$p/"; \
		find "$$d/$$p" -type f 2>/dev/null | sort | while read -r f; do \
			printf "%12d  %s\n" "$$(stat -c %s "$$f")" "$${f#$$d/}"; done; \
		find "$$d/$$p" -type f 2>/dev/null | xargs -r stat -c %s | awk -v p=$$p '{n++; t+=$$1} END {printf "%12d  total %s (%d files)\n", t, p, n}'; \
	done; \
	echo "== all"; du -sh "$$d" | awk '{print "   " $$1 " on disk"}'

reset-stories: docker ## Delete all stories so the next `make stories` rebuilds them from scratch
	@$(PSQL) -c "delete from stories;"

cluster: docker ## Batch experiment: re-cluster the whole window at each of THRESHOLDS (cluster_runs)
	$(DC) run --rm $(JOB_ENV) clusterer

open: ## Open the viewer in a browser
	@echo "Viewer: $(VIEWER_URL)"
	@if command -v xdg-open >/dev/null; then xdg-open "$(VIEWER_URL)" >/dev/null 2>&1 & \
	elif command -v open >/dev/null; then open "$(VIEWER_URL)"; \
	elif command -v wslview >/dev/null; then wslview "$(VIEWER_URL)"; fi

export: docker ## Save a run page as static HTML in out/: RUN=<id> (default latest), MIN_SOURCES=2
	@mkdir -p out; run=$(or $(RUN),$$($(PSQL) -tAc "select id from cluster_runs order by id desc limit 1")); \
	curl -fsS "$(VIEWER_URL)/runs/$$run?min_sources=$(MIN_SOURCES)" -o "out/run-$$run.html" \
		&& echo "Saved out/run-$$run.html"

export-editions: docker ## Save the side-by-side stories page (tabs) to out/editions.html: VIEW=top|latest
	@mkdir -p out; curl -fsS "$(VIEWER_URL)/editions?view=$(VIEW)&min_sources=$(MIN_SOURCES)" -o out/editions.html \
		&& echo "Saved out/editions.html"

ps: docker ## Show containers
	$(DC) --profile jobs ps -a

logs: docker ## Follow logs; SERVICE=viewer|db|s3|fn-scrape|... for one service
	$(DC) logs -f --tail=100 $(SERVICE)

health: docker ## Check the viewer and the database
	@$(WAIT_VIEWER) && echo "viewer: ok" || echo "viewer: not responding"
	@$(DC) exec -T db pg_isready -U seer -d seer -q && echo "db: ok" || echo "db: not responding"

stats: docker ## Articles per source and the latest cluster runs
	@$(PSQL) -c "select s.domain, count(a.id) as articles, max(a.published_at)::timestamp(0) as newest \
		from sources s left join articles a on a.source_id = s.id group by 1 order by 2 desc;" \
		-c "select id, threshold, article_count as articles, cluster_count as clusters, \
		multi_source_count as multi_source, largest_cluster as largest, created_at::timestamp(0) \
		from cluster_runs order by id desc limit 10;"

sql: docker ## Run one query: make sql SQL="select count(*) from articles"
	@$(PSQL) -c "$(SQL)"

psql: docker ## Open an interactive psql shell
	$(DC) exec db psql -U seer -d seer

clear-runs: docker ## Delete all cluster runs; articles and embeddings stay
	@$(PSQL) -c "delete from cluster_runs;"

clean: docker ## Stop everything and delete all data, including the model cache and data/s3
	$(DC) --profile jobs down -v
	@find $(S3_DIR) -mindepth 1 -delete 2>/dev/null || true
	rm -f certs/extra-ca.crt
