"""
Abstract base classes for AI providers.

The pipeline only ever talks to these interfaces. Concrete implementations
(OpenAI, Anthropic, ElevenLabs, Mock, ...) live in sibling modules and are
selected by factory functions in `llm.py`, `tts.py`, `image.py`.

This indirection means:
  - Adding a new provider = one new module + one line in the factory.
  - Testing the pipeline = inject a Mock provider.
  - Running without API keys = Mock provider is auto-selected.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


# ----- LLM -----

@dataclass
class LLMMessage:
    role: str  # 'system' | 'user' | 'assistant'
    content: str


@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    json_mode: bool = False
    model_hint: str | None = None  # 'small' | 'large' — provider maps to a model
    temperature: float = 0.7
    max_tokens: int = 2048


@dataclass
class LLMResponse:
    content: str
    parsed_json: dict | None = None
    usage: dict = field(default_factory=dict)


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse: ...


# ----- TTS -----

@dataclass
class TTSRequest:
    text: str
    output_path: str  # Where to write the audio file (mp3/wav).
    voice_id: str | None = None
    language: str = "en"


@dataclass
class TTSResponse:
    audio_path: str
    word_timestamps: list[dict]  # [{word, start_sec, end_sec}]
    duration_sec: float


class TTSProvider(ABC):
    name: str = "base"

    @abstractmethod
    def synthesize(self, request: TTSRequest) -> TTSResponse: ...


# ----- Image generation -----

@dataclass
class ImageRequest:
    prompt: str
    output_path: str
    width: int = 1920
    height: int = 1080
    style_hint: str | None = None


@dataclass
class ImageResponse:
    image_path: str


class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, request: ImageRequest) -> ImageResponse: ...


# ----- Search -----

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    tier: str = "TIER3"
    published_date: str = ""


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, tier_hint: str | None = None) -> list[SearchResult]: ...


# ----- Content Fetch -----

@dataclass
class FetchResult:
    url: str
    title: str
    text_content: str
    published_date: str = ""
    author: str = ""
    domain: str = ""


class ContentFetchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, url: str) -> FetchResult | None: ...


# ----- Video generation -----
# Tích hợp các AI video provider miễn phí: Kivest, Veo 3.1, Kling, ...
# Khi project mở rộng để sinh B-roll footage, animation B-roll sẽ dùng các provider này.

@dataclass
class VideoRequest:
    """Request tạo video từ text prompt hoặc image-to-video."""
    prompt: str
    output_path: str                       # Path lưu file MP4
    duration_sec: int = 8                  # Độ dài video (giây)
    aspect_ratio: str = "16:9"             # "16:9" | "9:16" | "1:1"
    quality: str = "standard"              # "draft" | "standard" | "high"
    reference_image_path: str | None = None  # For image-to-video
    seed: int | None = None                # Để tái tạo kết quả


@dataclass
class VideoResponse:
    """Kết quả generate video."""
    video_path: str
    duration_sec: float
    provider: str                          # Tên provider đã dùng
    model: str                             # Model cụ thể
    cost_estimate_usd: float = 0.0         # Ước tính chi phí (cho monitoring)


class VideoProvider(ABC):
    """Abstract base cho mọi AI video generation provider."""
    name: str = "base"

    @abstractmethod
    def generate(self, request: VideoRequest) -> VideoResponse: ...

    @abstractmethod
    def is_available(self) -> bool:
        """Kiểm tra provider có sẵn sàng (đủ API key, không bị rate-limit, v.v.)."""
        ...

