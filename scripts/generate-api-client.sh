#!/usr/bin/env bash
# Generate TypeScript API client from FastAPI's OpenAPI spec.
# Requires: API server running, npx available.
# Usage: make generate-client
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"
OUTPUT_DIR="$FRONTEND_DIR/src/api/generated"

echo "Fetching OpenAPI spec from $API_URL/openapi.json..."
curl -sf "$API_URL/openapi.json" -o /tmp/stratum-openapi.json

echo "Generating TypeScript types..."
mkdir -p "$OUTPUT_DIR"
cd "$FRONTEND_DIR"
npx openapi-typescript /tmp/stratum-openapi.json -o "$OUTPUT_DIR/schema.ts"

echo "Generated: $OUTPUT_DIR/schema.ts"
