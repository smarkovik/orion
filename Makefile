# Makefile for Orion API Docker operations

.PHONY: help build run stop clean dev logs shell test

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
	@echo "  test      - Test the API endpoints"

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

# Test API endpoints
test:
	@echo "Testing API endpoints..."
	@echo "1. Testing root endpoint:"
	@curl -s http://localhost:8000/ | jq .
	@echo "\n2. Testing health endpoint:"
	@curl -s http://localhost:8000/health | jq .
	@echo "\n3. Testing query endpoint:"
	@curl -s -X POST http://localhost:8000/v1/query \
		-H "Content-Type: application/json" \
		-d '{"body": {"query": "SELECT * FROM users"}}' | jq .
	@echo "\n4. Testing upload endpoint:"
	@echo "test content" > /tmp/test.txt
	@curl -s -X POST http://localhost:8000/v1/upload \
		-F "file=@/tmp/test.txt" \
		-F "email=test@example.com" \
		-F "description=Test file" | jq .
	@rm -f /tmp/test.txt
