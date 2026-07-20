#!/bin/bash
echo "==================================="
echo "  VideoDub - Development Mode"
echo "==================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker Desktop or Docker daemon."
    exit 1
fi

# Use docker compose (v2) or docker-compose (v1)
COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null; then
    COMPOSE_CMD="docker-compose"
fi

echo "[1/3] Building development images..."
$COMPOSE_CMD -f docker-compose.dev.yml build

echo ""
echo "[2/3] Starting development containers..."
$COMPOSE_CMD -f docker-compose.dev.yml up -d

echo ""
echo "[3/3] Waiting for services to be ready..."
sleep 5

if $COMPOSE_CMD -f docker-compose.dev.yml ps | grep -q "Up"; then
    echo ""
    echo "==================================="
    echo "  VideoDub Development Mode Running!"
    echo "  Frontend: http://localhost:5173"
    echo "  Backend:  http://localhost:8000"
    echo "  API Docs: http://localhost:8000/docs"
    echo "==================================="
    echo ""
    echo "Use '$COMPOSE_CMD -f docker-compose.dev.yml logs -f' to view logs"
    echo "Use '$COMPOSE_CMD -f docker-compose.dev.yml down' to stop"
else
    echo ""
    echo "Error: Some containers failed to start."
    echo "Check logs with: $COMPOSE_CMD -f docker-compose.dev.yml logs"
    exit 1
fi