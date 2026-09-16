"""Test Image providers."""
import sys
sys.path.insert(0, ".")
from pathlib import Path

print("=" * 60)
print("TEST IMAGE PROVIDERS")
print("=" * 60)

out_dir = Path("./workspace/_test_images")
out_dir.mkdir(parents=True, exist_ok=True)

# Test 1: Placeholder
print("\n[1] PLACEHOLDER (always works)")
from app.providers.placeholder_image import PlaceholderImageProvider
from app.providers.base import ImageRequest

try:
    p = PlaceholderImageProvider()
    out = str(out_dir / "placeholder_test.png")
    req = ImageRequest(
        prompt="A beautiful sunset over the ocean",
        output_path=out,
        width=512,
        height=512,
    )
    resp = p.generate(req)
    sz = Path(resp.image_path).stat().st_size
    print(f"[OK] Image: {resp.image_path}")
    print(f"     Size: {sz} bytes ({sz/1024:.1f} KB)")
except Exception as e:
    print(f"[FAIL] Placeholder: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Image factory
print("\n[2] IMAGE FACTORY")
try:
    from app.providers.image import get_image_provider
    provider = get_image_provider()
    print(f"     Active provider: {type(provider).__name__}")
    out = str(out_dir / "factory_test.png")
    req = ImageRequest(
        prompt="Mountain landscape at dawn",
        output_path=out,
        width=512,
        height=512,
    )
    resp = provider.generate(req)
    print(f"[OK] Image: {resp.image_path}")
    print(f"     Size: {Path(resp.image_path).stat().st_size} bytes")
except Exception as e:
    print(f"[FAIL] Factory: {e}")
    import traceback
    traceback.print_exc()
