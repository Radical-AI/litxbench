# List available recipes
default:
    @just --list

# Build docs + explorer and preview locally
docs:
    uv run sphinx-build docs docs/_build/html
    cd ui && bash build-static.sh
    rm -rf docs/_build/html/explorer
    cp -r ui/out docs/_build/html/explorer
    rm -rf /tmp/litxbench-preview
    mkdir -p /tmp/litxbench-preview/litxbench
    cp -r docs/_build/html/* /tmp/litxbench-preview/litxbench/
    @echo "Docs:     http://localhost:8000/litxbench/"
    @echo "Explorer: http://localhost:8000/litxbench/explorer/"
    python3 -m http.server 8000 --directory /tmp/litxbench-preview

# Run the UI dev server (includes transcribe page)
ui:
    cd ui && npm install && npm run dev

# Regenerate the graph JSON from the dataset
graph:
    uv run python scripts/ast_to_graph.py

# Clean build artifacts
clean:
    rm -rf docs/_build ui/out ui/.next /tmp/litxbench-preview
