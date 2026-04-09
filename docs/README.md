# Development notes

## Prerequisites

Install the [just](https://github.com/casey/just) command runner:

```bash
# macOS
brew install just

# Linux
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
```

## Build & preview

From the project root, build and preview the docs locally:

```bash
just docs
```

Then open:
- Docs: http://localhost:8000/litxbench/
- Explorer: http://localhost:8000/litxbench/explorer/
