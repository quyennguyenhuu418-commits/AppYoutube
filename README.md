# AI Documentary Animation Factory

Hệ thống sản xuất video documentary bằng AI - **nhập chủ đề, xuất video**.

> Giao diện: **Tiếng Việt** | Nội dung video: **Tiếng Anh (US/UK)**

> Hệ thống bắt chước phong cách của các kênh documentary 2D / stick-figure giáo dục hiện đại (câu hỏi thúc đẩy tò mò, commentary bằng giọng nói, nhân vật đơn giản, camera động, infographic animation), nhưng hoàn toàn tự sáng tạo về hình ảnh và văn bản.

> Người dùng nhập chủ đề (ví dụ: `How Did Ancient Humans Survive Deadly Winters?`), hệ thống sẽ tự động: nghiên cứu → luận điểm → tiêu đề → kịch bản → storyboard → tài nguyên nhân vật/background → audio narration → scene JSON → render video → cắt Short 9:16 → sinh thumbnail → chuẩn bị xuất bản đa nền tảng.

**Nguyên tắc thiết kế cốt lõi**: LLM **không bao giờ viết code video trực tiếp**. LLM chỉ xuất JSON `SceneDefinition` nghiêm ngặt, animation và hình học thực sự do renderer tất định (Remotion) thực thi.

---

## Tính năng đã hoàn thành

- **Backend FastAPI** với **13 stages pipeline** (s1→s13: từ nghiên cứu → xuất bản)
- **Groq LLM Provider** (MIỄN PHÍ, NHANH) - dùng `groq/compound-mini`
- **Cursor SDK Provider** - dùng Modal Agent để research/script
- **OpenAI/ElevenLabs** providers (tùy chọn)
- **Mock LLM Provider** - chạy demo không cần API key
- **FFmpeg** - render video thực
- **Remotion renderer** - video composition
- **Next.js webapp** - giao diện quản lý
- **P13 Shorts Generator** - cắt clip dọc 9:16 (TikTok/Reels)
- **P14 Thumbnail Generator** - ảnh thumbnail YouTube/Twitter/Instagram
- **P15 Multi-platform Publishing** - metadata cho YouTube + TikTok + Facebook
- **P16 Real Platform API Clients** - credential-based YouTube/TikTok/Facebook clients
- **Research Engine v16.5** - phát hiện mâu thuẫn, trích xuất địa điểm + số liệu

---

## Cài đặt nhanh (Windows)

### Yêu cầu hệ thống
- Python 3.11+ (đã cài)
- Node.js 20+ (cài từ https://nodejs.org)
- FFmpeg (đã cài tại `C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin`)

### Bước 1: Khởi động Backend
```powershell
cd C:\Users\Administrator\Downloads\video\AppYoutube
.\orchestrator\.venv\Scripts\activate
cd orchestrator
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Bước 2: Khởi động Frontend (terminal khác)
```powershell
cd C:\Users\Administrator\Downloads\video\AppYoutube\webapp
npm install
npm run dev
```

Mở trình duyệt: http://localhost:3000

### Hoặc dùng `start.bat` (khuyến nghị)
```cmd
cd C:\Users\Administrator\Downloads\video\AppYoutube
start.bat
```

---

## API Endpoints

### Health Check
```
GET http://localhost:8000/health
```
Response mẫu:
```json
{
  "status": "ok",
  "openai_configured": false,
  "groq_configured": true,
  "cursor_configured": false,
  "elevenlabs_configured": false,
  "cache_mode": "always",
  "groq_model": "groq/compound-mini"
}
```

### Tạo job video
```
POST http://localhost:8000/jobs
Content-Type: application/json

{
  "topic": "How Did Ancient Humans Survive Deadly Winters?",
  "duration_sec": 120,
  "language": "en"
}
```

### Check trạng thái job
```
GET http://localhost:8000/jobs/{job_id}
```

### Distribution (sau khi job hoàn thành)
```
# Sinh Shorts 9:16
GET http://localhost:8000/jobs/{job_id}/shorts

# Sinh thumbnails
GET http://localhost:8000/jobs/{job_id}/thumbnails

# Lên kế hoạch xuất bản YouTube/TikTok/Facebook
POST http://localhost:8000/publishing/preflight
POST http://localhost:8000/publishing/finalize
GET http://localhost:8000/publishing/{job_id}/plan
```

---

## Lấy Cursor API Key

Lưu ý quan trọng: Cursor API key **chỉ tạo được trên web dashboard**, không tạo được trong IDE.

### Cách lấy:
1. Mở trình duyệt: https://cursor.com/dashboard/integrations
2. Đăng nhập bằng tài khoản Cursor của bạn
3. Click **"New API Key"**
4. Copy key (dạng `cursor_xxxxxxxxxx`)
5. Thêm vào `.env`:
   ```
   CURSOR_API_KEY=cursor_xxxxxxxxxx
   ```

### Nếu không có API key
Vẫn dùng được Cursor Modal qua **Cursor IDE chat** (Ctrl+I / Cmd+I). Nhưng không tự động hóa được từ pipeline.

## LLM Providers (ưu tiên theo thứ tự)

| Provider | Chi phí | Tốc độ | Chất lượng | Cài đặt |
|----------|---------|--------|-----------|---------|
| **Cursor SDK** | Dùng request của bạn | Rất nhanh | ⭐⭐⭐⭐⭐ | Cần `CURSOR_API_KEY` |
| **Groq** | MIỄN PHÍ | Cực nhanh | ⭐⭐⭐⭐ | Đã cấu hình |
| **OpenAI** | $$$ | Nhanh | ⭐⭐⭐⭐⭐ | Cần `OPENAI_API_KEY` |
| **Mock** | MIỄN PHÍ | Cực nhanh | Demo | Mặc định |

---

## Test thủ công

### Test Groq Provider
```powershell
cd orchestrator
.\.venv\Scripts\python.exe test_groq_provider.py
```

### Test Cursor Agent (cần CURSOR_API_KEY)
```powershell
cd orchestrator
.\.venv\Scripts\python.exe demo_cursor_agent.py
```

### Test Pipeline đầy đủ
```powershell
cd scripts
..\orchestrator\.venv\Scripts\python.exe editorial_smoke_test.py
```

---

## Cấu trúc dự án

```
AppYoutube/
├── orchestrator/              # Python FastAPI backend
│   ├── app/
│   │   ├── providers/        # LLM, TTS, Image, Search providers
│   │   │   ├── groq_llm.py   # ← Groq provider (MIỄN PHÍ!)
│   │   │   ├── cursor_agent.py  # ← Cursor SDK provider
│   │   │   ├── openai_llm.py
│   │   │   └── mock_llm.py
│   │   ├── pipeline/         # 13-stage video generation pipeline
│   │   │   └── stages/       # s1_research → s13_publishing
│   │   ├── shorts/           # P13: 9:16 short clips
│   │   ├── thumbnail/        # P14: YouTube/Twitter thumbnails
│   │   ├── publishing/       # P15+P16: multi-platform publishing
│   │   ├── api/              # FastAPI routes
│   │   └── main.py
│   ├── .venv/                # Python virtual environment
│   ├── requirements.txt
│   └── tests/                # 1673+ Python tests
├── renderer/                  # Node.js Remotion video renderer
├── webapp/                    # Next.js frontend
│   └── app/jobs/[id]/
│       ├── shorts/page.tsx       # P13
│       ├── thumbnails/page.tsx   # P14
│       └── publishing/page.tsx   # P15+P16
├── workspace/                 # Job outputs (gitignored)
├── docs/                      # Tài liệu dự án
├── .env                       # API keys
└── start.bat                  # Launcher một lệnh
```

---

## Biến môi trường

Xem file `.env` để biết tất cả biến môi trường. Các biến quan trọng:

```bash
# LLM Providers
GROQ_API_KEY=...              # Miễn phí, đã có
OPENAI_API_KEY=...            # Trả phí
CURSOR_API_KEY=...            # Dùng Modal của bạn
GEMINI_API_KEY_1=...          # Vision API
ELEVENLABS_API_KEY=...        # Voice generation

# Video defaults
DEFAULT_FPS=30
DEFAULT_WIDTH=1920
DEFAULT_HEIGHT=1080
TARGET_DURATION_SEC=120

# Publishing credentials (P16) — tùy chọn, để trống nếu chưa muốn publish
YOUTUBE_API_KEY=...           # YouTube Data API v3 key
YOUTUBE_CLIENT_ID=...         # OAuth 2.0
YOUTUBE_CLIENT_SECRET=...     # OAuth 2.0
YOUTUBE_REFRESH_TOKEN=...     # OAuth 2.0 refresh
TIKTOK_CLIENT_KEY=...         # TikTok for Developers
TIKTOK_CLIENT_SECRET=...      # TikTok for Developers
TIKTOK_ACCESS_TOKEN=...       # TikTok Login Kit
FACEBOOK_ACCESS_TOKEN=...     # Facebook Graph API
FACEBOOK_PAGE_ID=...          # Facebook Page ID
FACEBOOK_INSTAGRAM_ID=...     # Tùy chọn, để cross-post
```

---

## Tại sao Groq lại là lựa chọn tốt nhất?

1. **MIỄN PHÍ** với giới hạn rất cao (~30 req/phút)
2. **CỰC NHANH** (~500 tokens/sec)
3. **OpenAI-compatible API** - dùng chung SDK
4. **Model chất lượng cao** - `groq/compound-mini`, `qwen/qwen3.8-27b`

Groq được ưu tiên **trước** OpenAI trong pipeline. Khi cần task phức tạp (research đa bước, viết code), Cursor SDK sẽ được dùng.

---

## Tổng quan Pipeline (13 stages)

```
s1_research         →  Thu thập nguồn + trích xuất claims
s2_thesis           →  Xác định luận điểm cốt lõi
s3_titles           →  Sinh 5-10 tiêu đề viral
s4_script           →  Viết kịch bản ~120s
s5_storyboard       →  Chia scene với emotion + visual cue
s6_assets           →  Nhân vật + background assets
s7_narration        →  Audio giọng nói (TTS)
s8_scene_json       →  JSON scene canonical cho renderer
s9_validate         →  QA: validate schema, integrity, captions
s10_render          →  Final video (Remotion + FFmpeg)
s11_short           →  P13: Cắt 9:16 short clips
s12_thumbnail       →  P14: Sinh thumbnails
s13_publishing      →  P15+P16: Chuẩn bị metadata cho đa nền tảng
```

### Tính năng Distribution

Sau khi job hoàn thành, từ trang chi tiết job có thể truy cập:

- **Shorts** (`/jobs/[id]/shorts`) — 5-8 clip dọc 9:16 với captions repositioned
- **Thumbnails** (`/jobs/[id]/thumbnails`) — Title cards + scene captures (4 variants: title, scene, social, square)
- **Publishing** (`/jobs/[id]/publishing`) — Form chọn nền tảng + metadata + preflight check

---

## Troubleshooting

### Lỗi "python not recognized"
- Cài lại Python và tick "Add Python to PATH"
- Hoặc dùng đường dẫn đầy đủ: `C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe`

### Lỗi "ffmpeg not recognized"
- Thêm vào PATH: `C:\ffmpeg\ffmpeg-9.0.1-essentials_build\bin`
- Hoặc restart máy sau khi cài

### Lỗi CORS_ORIGINS
- pydantic-settings 2.15 yêu cầu JSON list
- Fix đã có trong `app/core/config.py` (dùng `NoDecode`)

### Model not found (Groq)
- Groq đã ngừng hỗ trợ `llama-3.1-*`, dùng `groq/compound-mini` hoặc `qwen/qwen3.8-27b`

### Publishing trả về RATE_LIMITED
- Đây là stub — để enable real uploads cần:
  1. Install `httpx` hoặc `aiohttp`
  2. Cấu hình OAuth credentials trong `.env`
  3. Implement actual HTTP calls trong `app/publishing/platform_client.py`

---

## Hỗ trợ

- **Docs**: Xem `docs/` folder
- **Issues**: Tạo issue trên GitHub
- **Cursor API**: https://cursor.com/dashboard/integrations
- **Groq Console**: https://console.groq.com

---

## Roadmap tổng quan

```
P0  → P12      HOÀN THÀNH (Foundation + Render + Pipeline)
P13 Shorts     ✅ HOÀN THÀNH
P14 Thumbnails ✅ HOÀN THÀNH
P15 Publishing ✅ HOÀN THÀNH
P16 Real APIs  ✅ HOÀN THÀNH (Client layer, cần HTTP cho live upload)
P16.5 Research ✅ HOÀN THÀNH

Future work:
  - Analytics dashboard
  - Multi-user + Auth
  - Real OAuth HTTP uploads (YouTube/TikTok/Facebook)
  - Animation Engine cho renderer
```

---

## Tóm tắt kỹ thuật

| Thành phần | Trạng thái | Tests |
|------------|-----------|-------|
| Pipeline (s1-s13) | ✅ 13 stages | 180+ pass |
| Shorts | ✅ 9:16 generator | 23 tests |
| Thumbnails | ✅ Multi-variant | 15 tests |
| Publishing metadata | ✅ 3 platforms | 29 tests |
| Platform API clients | ✅ Stub interface | 16 tests |
| Research engine | ✅ 5 extractors | 8 tests |
| Web UI | ✅ 3 distribution pages | — |
