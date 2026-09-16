"""Test Groq provider via app config."""
import sys
sys.path.insert(0, ".")

from app.core.config import settings
from app.providers.groq_llm import GroqLLMProvider
from app.providers.base import LLMRequest, LLMMessage

print(f"Groq API Key configured: {bool(settings.groq_api_key)}")
print(f"Groq Model: {settings.groq_llm_model}")

provider = GroqLLMProvider()
print(f"Provider: {provider.name}")

req = LLMRequest(
    messages=[
        LLMMessage(role="system", content="You are helpful."),
        LLMMessage(role="user", content="Say 'Groq works!' in 3 words"),
    ],
    max_tokens=20,
)

resp = provider.complete(req)
print(f"Response: {resp.content}")
print(f"Usage: {resp.usage}")
