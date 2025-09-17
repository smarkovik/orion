# Makefile for Orion API Docker operations

.PHONY: help build run stop clean dev logs shell test unit-test coverage check-reqs

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
	@echo "  unit-test - Run all unit tests, integration tests, and comprehensive tests"
	@echo "  coverage  - Run unit tests with coverage analysis only"
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

# Run all tests (unit tests, integration tests, and comprehensive tests)
unit-test:
	@echo "🧪 Running All Orion Tests"
	@echo "=========================="
	@echo ""
	@echo "📋 1. Installing development dependencies..."
	pip install -r requirements-dev.txt
	@echo ""
	@echo "🔬 2. Running unit tests with coverage..."
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
	@echo ""
	@echo "🏗️  3. Running SDK tests..."
	cd sdk && python -m pytest tests/ -v
	@echo ""
	@echo "🚀 4. Running comprehensive document processing test..."
	./scripts/quick_test.sh
	@echo ""
	@echo "📊 5. Running full workflow test..."
	./scripts/test_full_workflow.sh
	@echo ""
	@echo "📈 6. Coverage Report Summary..."
	@echo "HTML coverage report generated in: htmlcov/index.html"
	@echo "Open with: open htmlcov/index.html"
	@echo ""
	@echo "🎉 All tests completed with coverage analysis!"

# Run unit tests with coverage analysis only
coverage:
	@echo "🔬 Running Unit Tests with Coverage Analysis"
	@echo "============================================"
	@echo ""
	@echo "📋 Installing development dependencies..."
	pip install -r requirements-dev.txt
	@echo ""
	@echo "🧪 Running pytest with coverage..."
	pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html --cov-fail-under=80
	@echo ""
	@echo "📈 Coverage Report Generated!"
	@echo "HTML report: htmlcov/index.html"
	@echo "Open with: open htmlcov/index.html"
