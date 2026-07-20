#!/bin/bash
echo "==================================="
echo "  VideoDub - Docker Build & Run"
echo "==================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop or Docker daemon."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "Error: docker-compose is not installed."
    exit 1
fi

# Use docker compose (v2) or docker-compose (v1)
COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
fi

echo "[1/4] Creating necessary directories..."
mkdir -p backend/temp backend/output backend/cookies

echo "[2/4] Building Docker images..."
$COMPOSE_CMD build

echo ""
echo "[3/4] Starting containers..."
$COMPOSE_CMD up -d

echo ""
echo "[4/4] Waiting for services to be ready..."
sleep 5

# Check if containers are running
if $COMPOSE_CMD ps | grep -q "Up"; then
    echo ""
    echo "==================================="
    echo "  VideoDub is running in Docker!"
    echo "  Frontend: http://localhost:3000"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "==================================="
    echo ""
    echo "Use '$COMPOSE_CMD logs -f' to view logs"
    echo "Use '$COMPOSE_CMD down' to stop"
else
    echo ""
    echo "Error: Some containers failed to start."
    echo "Check logs with: $COMPOSE_CMD logs"
    exit 1
fi