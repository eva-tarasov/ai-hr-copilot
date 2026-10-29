"""Environment-backed provider selection for application composition."""

from backend.app.core.config import Settings
from backend.app.llm.errors import ProviderError
from backend.app.llm.fake import FakeProvider
from backend.app.llm.openai_provider import OpenAIProvider
from backend.app.llm.provider import LLMProvider


def make_provider(settings: Settings) -> LLMProvider:
    selected = settings.llm_provider.strip().lower()
    if selected == "fake":
        return FakeProvider()
    if selected == "openai":
        return OpenAIProvider(model=settings.openai_model, api_key=settings.openai_api_key)
    raise ProviderError("unsupported_provider")
