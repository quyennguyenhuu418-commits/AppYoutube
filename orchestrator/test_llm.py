"""Test all LLM providers using the standard LLMRequest interface."""
import sys
sys.path.insert(0, ".")

from app.providers.base import LLMRequest, LLMMessage

print("=" * 60)
print("TEST 1: GROQ LLM (FREE)")
print("=" * 60)

from app.providers.groq_llm import GroqLLMProvider

try:
    p = GroqLLMProvider()
    req = LLMRequest(
        messages=[LLMMessage(role="user", content="What is 2+2? One sentence.")],
        max_tokens=30,
        temperature=0,
    )
    r = p.complete(req)
    print(f"[OK] Response: {r.content[:120]}")
    print(f"     Usage: {r.usage}")
except Exception as e:
    print(f"[FAIL] {e}")

print()
print("=" * 60)
print("TEST 2: GEMINI with rotation")
print("=" * 60)

from app.providers.gemini import GeminiRotatingProvider

try:
    p = GeminiRotatingProvider()
    print(f"Keys: {p.get_status()}")
    text = p.generate("What is 2+2? Answer in one sentence.", max_output_tokens=30)
    print(f"[OK] Gemini response: {text[:120]}")
    print(f"     Status: {p.get_status()}")
except Exception as e:
    print(f"[FAIL] Gemini: {e}")

print()
print("=" * 60)
print("TEST 3: LLM Factory (priority)")
print("=" * 60)

from app.providers.llm import get_llm_provider
provider = get_llm_provider()
print(f"Active provider: {type(provider).__name__}")

# Test that the factory-created provider also works
try:
    req = LLMRequest(
        messages=[LLMMessage(role="user", content="What is 2+2? One sentence.")],
        max_tokens=30,
        temperature=0,
    )
    r = provider.complete(req)
    print(f"[OK] Factory provider works: {r.content[:80]}")
except Exception as e:
    print(f"[FAIL] Factory provider: {e}")
