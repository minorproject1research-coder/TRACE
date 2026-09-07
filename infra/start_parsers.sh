#!/bin/bash
echo "Starting Docling + PDFFigures 2.0..."

cd "$(dirname "$0")"

docker-compose up -d docling pdffigures

echo ""
echo "Waiting for services to start (Docling models download on first run)..."
sleep 30

echo ""
echo "Checking service health..."
curl -f http://localhost:5001/health && echo " Docling: OK" || echo " Docling: FAILED"
curl -f http://localhost:4567/ && echo " PDFFigures: OK" || echo " PDFFigures: FAILED"

echo ""
echo "Services started!"
echo "  Docling: http://localhost:5001"
echo "  PDFFigures: http://localhost:4567"
echo ""
echo "Run 'python test_parse.py' to test parsing"
