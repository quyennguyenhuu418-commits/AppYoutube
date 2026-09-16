# AI Documentary Animation Factory

Hệ thống sản xuất video documentary bằng AI - **nhập chủ đề, xuất video**.

> Giao diện: **Tiếng Việt** | Nội dung video: **Tiếng Anh (US/UK)**

> Hệ thống bắt chước phong cách của các kênh documentary 2D / stick-figure giáo dục hiện đại (câu hỏi thúc đẩy tò mò, commentary bằng giọng nói, nhân vật đơn giản, camera động, infographic animation), nhưng hoàn toàn tự sáng tạo về hình ảnh và văn bản.

> Người dùng nhập chủ đề (ví dụ: `How Did Ancient Humans Survive Deadly Winters?`), hệ thống sẽ tự động: nghiên cứu → luận điểm → tiêu đề → kịch bản → storyboard → tài nguyên nhân vật/background → audio narration → scene JSON → render video → cắt Short 9:16.

> **Nguyên tắc thiết kế cốt lõi**: LLM **không bao giờ viết code video trực tiếp**. LLM chỉ xuất JSON `SceneDefinition` nghiêm ngặt, animation và hình học thực sự do renderer确定性 (Remotion) thực thi.

---

## 🚀 Tính năng đã hoàn thành

- ✅ **Backend FastAPI** với **13 stages pipeline** (s1→s13: research → publishing)
- ✅ **Groq LLM Provider** (MIỄN PHÍ, NHANH) - dùng `groq/compound-mini`
- ✅ **Cursor SDK Provider** - dùng Modal Agent để research/script
- ✅ **OpenAI/ElevenLabs** providers (optional)
- ✅ **Mock LLM Provider** - chạy demo không cần API key
- ✅ **FFmpeg** - render video thực
- ✅ **Remotion renderer** - video composition
- ✅ **Next.js webapp** - giao diện quản lý
- ✅ **P13 Shorts Generator** - 9:16 vertical clips (TikTok/Reels)
- ✅ **P14 Thumbnail Generator** - YouTube/Twitter/Instagram thumbnails
- ✅ **P15 Multi-platform Publishing** - metadata cho YouTube + TikTok + Facebook
- ✅ **P16 Real Platform API Clients** - credential-based YouTube/TikTok/Facebook clients
- ✅ **Research Engine v16.5** - contradiction detection, geographic + quantitative extraction

---

## 🔧 Cài đặt nhanh (Windows)

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

## 📡 API Endpoints

### Health Check
```
GET http://localhost:8000/health
```
Returns:
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

### Check job status
```
GET http://localhost:8000/jobs/{job_id}
```

### Distribution (after job completes)
```
# Generate 9:16 Shorts
GET http://localhost:8000/jobs/{job_id}/shorts

# Generate thumbnails
GET http://localhost:8000/jobs/{job_id}/thumbnails

# Plan publishing to YouTube/TikTok/Facebook
POST http://localhost:8000/publishing/preflight
POST http://localhost:8000/publishing/finalize
GET http://localhost:8000/publishing/{job_id}/plan
```

---

## 🔑 Lấy Cursor API Key

⚠️ **Lưu ý quan trọng**: Cursor API key **chỉ tạo được trên web dashboard**, không tạo được trong IDE.

### Cách lấy:
1. Mở browser: https://cursor.com/dashboard/integrations
2. Đăng nhập bằng tài khoản Cursor của bạn
3. Click **"New API Key"**
4. Copy key (dạng `cursor_xxxxxxxxxx`)
5. Thêm vào `.env`:
   ```
   CURSOR_API_KEY=cursor_xxxxxxxxxx
   ```

### Nếu không có API key
Vẫn dùng được Cursor Modal qua **Cursor IDE chat** (Ctrl+I / Cmd+I). Nhưng không tự động hóa được từ pipeline.

## 🤖 LLM Providers (ưu tiên theo thứ tự)

| Provider | Cost | Speed | Quality | Setup |
|----------|------|-------|---------|-------|
| **Cursor SDK** | Dùng request của bạn | ⚡⚡ | ⭐⭐⭐⭐⭐ | Cần `CURSOR_API_KEY` |
| **Groq** | FREE | ⚡⚡⚡ | ⭐⭐⭐ | ✅ Đã cấu hình |
| **OpenAI** | $$$ | ⚡⚡ | ⭐⭐⭐⭐⭐ | Cần `OPENAI_API_KEY` |
| **Mock** | FREE | ⚡⚡⚡ | Demo | Mặc định |

---

## 🧪 Test thủ công

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

## 📁 Cấu trúc dự án

```
AppYoutube/
├── orchestrator/              # Python FastAPI backend
│   ├── app/
│   │   ├── providers/        # LLM, TTS, Image, Search providers
│   │   │   ├── groq_llm.py   # ← Groq provider (FREE!)
│   │   │   ├── cursor_agent.py  # ← Cursor SDK provider
│   │   │   ├── openai_llm.py
│   │   │   └── mock_llm.py
│   │   ├── pipeline/         # 11-stage video generation pipeline
│   │   │   └── stages/       # s1_research → s11_short
│   │   ├── api/              # FastAPI routes
│   │   └── main.py
│   ├── .venv/                # Python virtual environment
│   ├── requirements.txt
│   └── test_groq_provider.py
├── renderer/                  # Node.js Remotion video renderer
├── webapp/                    # Next.js frontend
├── workspace/                 # Job outputs (gitignored)
├── .env                       # API keys
└── start.bat                  # One-click launcher
```

---

## 🔑 Environment Variables

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

# Publishing credentials (P16) — optional, để trống nếu chưa muốn publish
YOUTUBE_API_KEY=...           # YouTube Data API v3 key
YOUTUBE_CLIENT_ID=...         # OAuth 2.0
YOUTUBE_CLIENT_SECRET=...     # OAuth 2.0
YOUTUBE_REFRESH_TOKEN=...     # OAuth 2.0 refresh
TIKTOK_CLIENT_KEY=...         # TikTok for Developers
TIKTOK_CLIENT_SECRET=...      # TikTok for Developers
TIKTOK_ACCESS_TOKEN=...       # TikTok Login Kit
FACEBOOK_ACCESS_TOKEN=...     # Facebook Graph API
FACEBOOK_PAGE_ID=...          # Facebook Page ID
FACEBOOK_INSTAGRAM_ID=...     # Optional, for cross-post
```

---

## 💡 Tại sao Groq lại là lựa chọn tốt nhất?

1. **MIỄN PHÍ** với giới hạn rất cao (~30 req/phút)
2. **CỰC NHANH** (~500 tokens/sec)
3. **OpenAI-compatible API** - dùng chung SDK
4. **Model chất lượng cao** - `groq/compound-mini`, `qwen/qwen3.8-27b`

Groq được ưu tiên **trước** OpenAI trong pipeline. Khi cần task phức tạp (research đa bước, viết code), Cursor SDK sẽ được dùng.

---

## 🐛 Troubleshooting

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

---

## 📞 Support

- Docs: Xem `docs/` folder
- Issues: Tạo issue trên GitHub
- Cursor API: https://cursor.com/dashboard/integrations
- Groq Console: https://console.groq.com
