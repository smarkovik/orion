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
IMAGES := viewer scraper clusterer
WAIT_VIEWER := (for _ in $$(seq 1 30); do curl -fsS "$(VIEWER_URL)/healthz" >/dev/null 2>&1 && exit 0; sleep 1; done; exit 1)

# Optional per-run overrides, e.g. `make cluster THRESHOLDS=0.91,0.92`.
JOB_ENV := $(if $(HOURS),-e HOURS=$(HOURS)) $(if $(THRESHOLDS),-e THRESHOLDS=$(THRESHOLDS)) \
	$(if $(WINDOW_HOURS),-e WINDOW_HOURS=$(WINDOW_HOURS)) $(if $(MODEL),-e MODEL=$(MODEL))

.PHONY: help all docker certs build up down restart scrape cluster refresh open ps logs health stats sql psql \
	clear-runs clean

help: ## Show this list
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'
	@echo "  Variables: HOURS, THRESHOLDS, WINDOW_HOURS, MODEL, SERVICE, SQL, VIEWER_URL"

all: build up scrape cluster open ## Build, start, scrape, cluster, then open the viewer

refresh: scrape cluster ## Scrape new articles and re-cluster (containers already up)

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

up: docker ## Start the database and the viewer
	$(DC) up -d db viewer
	@$(WAIT_VIEWER) || echo "viewer: not ready after 30 s; see make logs SERVICE=viewer"

down: docker ## Stop all containers; data is kept
	$(DC) --profile jobs down

restart: docker ## Restart the viewer
	$(DC) restart viewer

scrape: docker ## Scrape the last HOURS (default 48) from all sources
	$(DC) run --rm $(JOB_ENV) scraper

cluster: docker ## Embed new articles and cluster at each of THRESHOLDS
	$(DC) run --rm $(JOB_ENV) clusterer

open: ## Open the viewer in a browser
	@echo "Viewer: $(VIEWER_URL)"
	@if command -v xdg-open >/dev/null; then xdg-open "$(VIEWER_URL)" >/dev/null 2>&1 & \
	elif command -v open >/dev/null; then open "$(VIEWER_URL)"; \
	elif command -v wslview >/dev/null; then wslview "$(VIEWER_URL)"; fi

ps: docker ## Show containers
	$(DC) --profile jobs ps -a

logs: docker ## Follow logs; SERVICE=viewer|db for one service
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

clean: docker ## Stop everything and delete all data, including the model cache
	$(DC) --profile jobs down -v
	rm -f certs/extra-ca.crt
