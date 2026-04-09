# Transcribe & Extract

The transcribe feature processes PDFs using OCR and LLM extraction to produce structured experiment graphs. It requires running the UI locally with API keys configured.

## Prerequisites

1. **Clone the repository**

   ```bash
   git clone https://github.com/Radical-AI/litxbench.git && cd litxbench
   ```

2. **Install [Node.js](https://nodejs.org) (includes npm)**

   Required to host the UI locally. Download from nodejs.org or use a version manager.

   ```bash
   # macOS
   brew install node

   # Or use nvm (any platform)
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   nvm install 20
   ```

3. **Install the [just](https://github.com/casey/just) command runner**

   Used to run project tasks like starting the dev server.

   ```bash
   # macOS
   brew install just

   # Linux
   curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to /usr/local/bin
   ```

4. **Install with paper dependencies**

   This includes the pydantic-ai dependency needed for extraction.

   ```bash
   uv sync --group paper
   ```

5. **Set your API keys**

   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   export MISTRAL_API_KEY="your-mistral-ocr-key"
   ```

6. **Start the UI**

   ```bash
   just ui
   ```

   Then open http://localhost:3000/transcribe to upload and process PDFs.

## How It Works

The pipeline runs two stages:

1. **OCR** -- The PDF is sent to [Mistral OCR 3](https://mistral.ai) which converts pages into markdown text with images.
2. **Extraction** -- The transcribed text is passed to [Gemini 3 Flash](https://ai.google.dev) which extracts structured experiment data.

Results are displayed as an interactive process graph in the browser.
