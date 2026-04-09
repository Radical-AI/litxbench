#!/bin/bash
# Build the UI for static GitHub Pages deployment.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Clean previous build artifacts to avoid stale caches
rm -rf .next out

# Temporarily move server-only routes out of the build
mv src/app/api src/app/_api_bak

trap 'mv src/app/_api_bak src/app/api 2>/dev/null' EXIT

# STATIC_EXPORT=true triggers next.config.ts to enable static export (output: "export",
# basePath, etc.) and sets NEXT_PUBLIC_STATIC_EXPORT so the transcribe page shows
# setup instructions instead of the interactive UI.
STATIC_EXPORT=true npm run build

echo "Static export ready at: out/"
