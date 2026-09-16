"""Test all API keys in .env to find which ones work/fail."""
import sys
sys.path.insert(0, ".")

from app.core.config import settings
from openai import OpenAI

print("=" * 60)
print("API KEY STATUS CHECK")
print("=" * 60)

# 1. Groq
print("\n[1] GROQ (FREE)")
if settings.groq_api_key:
    try:
        client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model="groq/compound-mini",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5
        )
        print("    [OK] Status: working")
    except Exception as e:
        print(f"    [FAIL] {str(e)[:120]}")
else:
    print("    MISSING")

# 2. OpenRouter
print("\n[2] OPENROUTER")
if settings.openrouter_api_key:
    try:
        client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        resp = client.chat.completions.create(
            model="anthropic/claude-3-haiku",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5
        )
        print("    [OK] Status: working")
    except Exception as e:
        print(f"    [FAIL] {str(e)[:120]}")
else:
    print("    MISSING")

# 3. Gemini - check rotation list
print("\n[3] GEMINI")
gemini_keys = getattr(settings, "gemini_api_keys", [])
if gemini_keys:
    print(f"    {len(gemini_keys)} key(s) configured for rotation")
    if gemini_keys[0].startswith("AQ."):
        print("    [INFO] Format: OAuth tokens (Google ADC)")
    else:
        print("    [INFO] Format: API keys")
else:
    print("    MISSING")

# 4. ElevenLabs
print("\n[4] ELEVENLABS")
el_key = getattr(settings, "elevenlabs_api_key", "") or ""
print("    configured" if el_key else "    MISSING")

# 5. Cursor SDK
print("\n[5] CURSOR SDK")
if settings.cursor_api_key:
    print("    configured")
else:
    print("    MISSING - get from https://cursor.com/dashboard/integrations")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"Groq:        {'OK' if settings.has_groq else 'MISSING'}")
print(f"OpenRouter:  {'configured' if settings.openrouter_api_key else 'MISSING'}")
print(f"Gemini:      {len(gemini_keys)} key(s) (rotation enabled)")
print(f"Cursor:      {'configured' if settings.cursor_api_key else 'MISSING'}")
print(f"ElevenLabs:  {'configured' if el_key else 'MISSING'}")
