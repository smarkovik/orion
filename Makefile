# Makefile for Orion API Docker operations

.PHONY: help build run stop clean dev logs shell test check-reqs

# Default target
help:
	@echo "Available commands:"
	@echo "  build     - Build the Docker image"
	@echo "  run       - Run the production container"
	@echo "  dev       - Run the development container with hot reload"
	@echo "  stop      - Stop all containers"
	@echo "  clean     - Remove containers and images"
	@echo "  logs      - Show container logs"
	@echo "  shell     - Open shell in running container"
	@echo "  test      - Run comprehensive document processing and search test"
	@echo "  check-reqs - Check requirements alignment"

# Build 
build:
	docker-compose build

# Run production
run:
	docker-compose up -d orion-api

# Run development with hot reload
dev:
	docker-compose --profile dev up -d orion-dev

# Stop all 
stop:
	docker-compose down

# Clean up 
clean:
	docker-compose down --rmi all --volumes --remove-orphans
	docker system prune -f

# logs
logs:
	docker-compose logs -f

# Open shell
shell:
	docker-compose exec orion-api /bin/bash

# Run comprehensive quick test
test:
	@echo "Running Orion comprehensive quick test..."
	./scripts/quick_test.sh
