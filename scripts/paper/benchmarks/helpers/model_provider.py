"""The model provider is a wrapper around pydantic-ai's model provider."""

import json
import logging
import os
from logging import Logger

from google.genai import Client
from google.genai.types import HttpOptions, HttpRetryOptions
from openai import AsyncAzureOpenAI
from openai.types.shared import ReasoningEffort
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel, GoogleModelName
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIChatModelSettings, OpenAIModelName
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

logger: Logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ModelProvider:
    """A provider for pydantic-ai models."""

    def __init__(self) -> None:
        pass

    def get_env(self, env_var_name: str) -> str:
        """Get value from environment variable."""
        value = os.getenv(env_var_name)
        if value is None:
            raise ValueError(f"{env_var_name} not configured")
        return value

    def ClaudeOpus41Model(self) -> AnthropicModel:
        """Returns an Opus 4.1 model."""
        return self._get_anthropic_model("claude-opus-4-1-20250805")

    def ClaudeOpus4Model(self) -> AnthropicModel:
        """Returns an Opus 4 model."""
        return self._get_anthropic_model("claude-opus-4-20250514")

    def ClaudeSonnet4Model(self) -> AnthropicModel:
        """Returns a Sonnet 4 model."""
        return self._get_anthropic_model("claude-sonnet-4-20250514")

    def ClaudeHaiku35Model(self) -> AnthropicModel:
        """Returns a Haiku 3.5 model."""
        return self._get_anthropic_model("claude-3-5-haiku-20241022")

    def ClaudeHaiku45Model(self) -> AnthropicModel:
        """Returns a Haiku 4.5 model."""
        return self._get_anthropic_model("claude-haiku-4-5")

    def ClaudeOpus45Model(self) -> AnthropicModel:
        """Returns an Opus 4.5 model."""
        return self._get_anthropic_model("claude-opus-4-5")

    def ClaudeOpus46Model(self) -> AnthropicModel:
        """Returns an Opus 4.6 model."""
        return self._get_anthropic_model("claude-opus-4-6")

    def ClaudeSonnet45Model(self) -> AnthropicModel:
        """Returns a Sonnet 4.5 model."""
        return self._get_anthropic_model("claude-sonnet-4-5")

    def Gemini25ProModel(self) -> GoogleModel:
        """Returns a Gemini 2.5 Pro model."""
        return self._get_google_model("gemini-2.5-pro")

    def Gemini25FlashModel(self) -> GoogleModel:
        """Returns a Gemini 2.5 Flash model."""
        return self._get_google_model("gemini-2.5-flash")

    def Gemini25FlashLiteModel(self) -> GoogleModel:
        """Returns a Gemini 2.5 Flash Lite model."""
        return self._get_google_model("gemini-2.5-flash-lite")

    def Gemini31FlashLiteModel(self) -> GoogleModel:
        """Returns a Gemini 3.1 Flash Lite model."""
        return self._get_google_model("gemini-3.1-flash-lite-preview")

    def Gemini3FlashModel(self) -> GoogleModel:
        """Returns a Gemini 3 Flash model."""
        return self._get_google_model("gemini-3-flash-preview")

    def Gemini3ProModel(self) -> GoogleModel:
        """Returns a Gemini 3 Pro model."""
        return self._get_google_model("gemini-3-pro-preview")

    def Gemini31ProModel(self) -> GoogleModel:
        """Returns a Gemini 3.1 Pro model."""
        return self._get_google_model("gemini-3.1-pro-preview")

    def GPT5Model(self, *, reasoning_effort: ReasoningEffort) -> OpenAIChatModel:
        """Returns a GPT-5 model."""
        return self._get_openai_model("gpt-5-2025-08-07", reasoning_effort=reasoning_effort)

    def GPT5MiniModel(self, reasoning_effort: ReasoningEffort | None = None) -> OpenAIChatModel:
        """Returns a GPT-5 mini model."""
        return self._get_openai_model("gpt-5-mini", reasoning_effort=reasoning_effort)

    def GPT4oModel(self) -> OpenAIChatModel:
        """Returns a GPT-4o model."""
        return self._get_openai_model("gpt-4o")

    def GPT5ProModel(self, reasoning_effort: ReasoningEffort) -> OpenAIChatModel:
        """Returns a GPT-5 Pro model."""
        return self._get_openai_model("gpt-5-pro", reasoning_effort=reasoning_effort)

    def GPT51Model(self, reasoning_effort: ReasoningEffort) -> OpenAIChatModel:
        """Returns a GPT-5.1 model."""
        return self._get_openai_model("gpt-5.1", reasoning_effort=reasoning_effort)

    def GPT52Model(self, reasoning_effort: ReasoningEffort) -> OpenAIChatModel:
        """Returns a GPT-5.2 model."""
        return self._get_openai_model("gpt-5.2", reasoning_effort=reasoning_effort)

    def _get_anthropic_model(self, model_name: str) -> AnthropicModel:
        """Create an Anthropic model instance.

        Backend selection (checked in order):
        1. ANTHROPIC_BACKEND env var explicitly set to "foundry" or "anthropic"
        2. ANTHROPIC_FOUNDRY_BASE_URL and ANTHROPIC_FOUNDRY_API_KEY present → Azure Foundry
        3. ANTHROPIC_API_KEY present → Anthropic API (default pydantic-ai behavior)
        4. Neither → raises ValueError
        """
        explicit_backend = os.getenv("ANTHROPIC_BACKEND", "").lower()
        has_foundry = bool(
            os.getenv("ANTHROPIC_FOUNDRY_BASE_URL") and os.getenv("ANTHROPIC_FOUNDRY_API_KEY")
        )
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))

        if explicit_backend == "foundry":
            use_foundry = True
        elif explicit_backend == "anthropic":
            use_foundry = False
        elif has_foundry and has_anthropic:
            logger.info(
                "Both Azure Foundry and Anthropic API keys found. "
                "Defaulting to Azure Foundry. Set ANTHROPIC_BACKEND=anthropic to override."
            )
            use_foundry = True
        elif has_foundry:
            use_foundry = True
        elif has_anthropic:
            use_foundry = False
        else:
            raise ValueError(
                "No Anthropic credentials found. Set ANTHROPIC_FOUNDRY_BASE_URL and "
                "ANTHROPIC_FOUNDRY_API_KEY for Azure Foundry, or ANTHROPIC_API_KEY for "
                "the Anthropic API. You can also set ANTHROPIC_BACKEND=foundry|anthropic "
                "to choose explicitly."
            )

        if use_foundry:
            provider = AnthropicProvider(
                base_url=self.get_env("ANTHROPIC_FOUNDRY_BASE_URL"),
                api_key=self.get_env("ANTHROPIC_FOUNDRY_API_KEY"),
            )
            return AnthropicModel(model_name, provider=provider)

        return AnthropicModel(model_name)

    def _get_google_model(self, model_name: GoogleModelName) -> GoogleModel:
        """Create a Google model instance.

        Backend selection (checked in order):
        1. GOOGLE_BACKEND env var explicitly set to "gemini" or "vertexai"
        2. GOOGLE_APPLICATION_CREDENTIALS present → Vertex AI
        3. GEMINI_API_KEY or GOOGLE_API_KEY present → Gemini API
        4. Neither → raises ValueError
        """
        explicit_backend = os.getenv("GOOGLE_BACKEND", "").lower()
        has_vertex_creds = bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

        if explicit_backend == "gemini":
            use_vertex = False
        elif explicit_backend == "vertexai":
            use_vertex = True
        elif has_vertex_creds and api_key:
            logger.info(
                "Both Vertex AI credentials and Gemini API key found. "
                "Defaulting to Vertex AI. Set GOOGLE_BACKEND=gemini to override."
            )
            use_vertex = True
        elif has_vertex_creds:
            use_vertex = True
        elif api_key:
            use_vertex = False
        else:
            raise ValueError(
                "No Google credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
                "for Vertex AI, or GEMINI_API_KEY / GOOGLE_API_KEY for the Gemini API. "
                "You can also set GOOGLE_BACKEND=gemini|vertexai to choose explicitly."
            )

        retry_options = HttpRetryOptions(
            attempts=10,
            initial_delay=1,
            max_delay=60,
            exp_base=2,
            http_status_codes=[429, 500, 503],
        )
        http_options = HttpOptions(retry_options=retry_options)

        if use_vertex:
            from google.oauth2 import service_account

            creds_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            with open(creds_path) as f:
                project = json.load(f).get("project_id")

            client = Client(
                vertexai=True,
                location="global",
                credentials=credentials,
                project=project,
                http_options=http_options,
            )
        else:
            client = Client(
                api_key=api_key,
                http_options=http_options,
            )

        provider = GoogleProvider(client=client)
        return GoogleModel(model_name, provider=provider)

    def _get_openai_model(
        self,
        model_name: OpenAIModelName,
        *,
        reasoning_effort: ReasoningEffort | None = None,
    ) -> OpenAIChatModel:
        """Create an OpenAI model instance.

        Backend selection (checked in order):
        1. OPENAI_BACKEND env var explicitly set to "azure" or "openai"
        2. AZURE_OPENAI_API_KEY present → Azure OpenAI
        3. OPENAI_API_KEY present → OpenAI API
        4. Neither → raises ValueError
        """
        explicit_backend = os.getenv("OPENAI_BACKEND", "").lower()
        has_azure = bool(os.getenv("AZURE_OPENAI_API_KEY"))
        has_openai = bool(os.getenv("OPENAI_API_KEY"))

        if explicit_backend == "azure":
            use_azure = True
        elif explicit_backend == "openai":
            use_azure = False
        elif has_azure and has_openai:
            logger.info(
                "Both Azure OpenAI and OpenAI API keys found. "
                "Defaulting to Azure. Set OPENAI_BACKEND=openai to override."
            )
            use_azure = True
        elif has_azure:
            use_azure = True
        elif has_openai:
            use_azure = False
        else:
            raise ValueError(
                "No OpenAI credentials found. Set AZURE_OPENAI_API_KEY (plus "
                "AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_VERSION) for Azure, "
                "or OPENAI_API_KEY for the OpenAI API. "
                "You can also set OPENAI_BACKEND=azure|openai to choose explicitly."
            )

        settings = (
            OpenAIChatModelSettings(openai_reasoning_effort=reasoning_effort)
            if reasoning_effort is not None
            else None
        )

        if use_azure:
            azure_client = AsyncAzureOpenAI(
                azure_endpoint=self.get_env("AZURE_OPENAI_ENDPOINT"),
                azure_deployment=model_name,
                api_key=self.get_env("AZURE_OPENAI_API_KEY"),
                api_version=self.get_env("AZURE_OPENAI_API_VERSION"),
            )
            provider = OpenAIProvider(openai_client=azure_client)
            return OpenAIChatModel(model_name, provider=provider, settings=settings)

        return OpenAIChatModel(model_name, settings=settings)


def get_model_from_name(provider: ModelProvider, model_name: str):
    """Get a model from its name."""
    match model_name:
        case "gemini-3.1-flash-lite":
            return provider.Gemini31FlashLiteModel()
        case "gemini-3-flash":
            return provider.Gemini3FlashModel()
        case "gemini-3-pro-preview":
            return provider.Gemini3ProModel()
        case "gemini-3.1-pro":
            return provider.Gemini31ProModel()
        case "gemini-2.5-pro":
            return provider.Gemini25ProModel()
        case "gemini-2.5-flash":
            return provider.Gemini25FlashModel()
        case "gemini-2.5-flash-lite":
            return provider.Gemini25FlashLiteModel()
        case "claude-haiku-4-5":
            return provider.ClaudeHaiku45Model()
        case "claude-opus-4-5":
            return provider.ClaudeOpus45Model()
        case "claude-opus-4-6":
            return provider.ClaudeOpus46Model()
        case "claude-sonnet-4-5":
            return provider.ClaudeSonnet45Model()
        case "gpt-5-minimal":
            return provider.GPT5Model(reasoning_effort="minimal")
        case "gpt-5-low":
            return provider.GPT5Model(reasoning_effort="low")
        case "gpt-5-medium":
            return provider.GPT5Model(reasoning_effort="medium")
        case "gpt-5-high":
            return provider.GPT5Model(reasoning_effort="high")
        case "gpt-5-pro-high":
            return provider.GPT5ProModel(reasoning_effort="high")
        case "gpt-5-1-low":
            return provider.GPT51Model(reasoning_effort="low")
        case "gpt-5-1-medium":
            return provider.GPT51Model(reasoning_effort="medium")
        case "gpt-5-2-medium":
            return provider.GPT52Model(reasoning_effort="medium")
        case "gpt-5-2-high":
            return provider.GPT52Model(reasoning_effort="high")
        case "gpt-5-2-xhigh":
            return provider.GPT52Model(reasoning_effort="xhigh")
        case "gpt-4o":
            return provider.GPT4oModel()
        case "gpt-5-mini-minimal":
            return provider.GPT5MiniModel(reasoning_effort="minimal")
        case "gpt-5-mini-medium":
            return provider.GPT5MiniModel(reasoning_effort="medium")
        case _:
            raise ValueError(f"Unknown provider name: {model_name}")
