# VideoDub — Ứng dụng Lồng Tiếng Video Bằng AI

> **100% MIỄN PHÍ** · Chạy hoàn toàn local · Không gửi dữ liệu ra ngoài

VideoDub là công cụ lồng tiếng video tự động sử dụng AI: tải video → sinh phụ đề (Whisper) → dịch thuật → TTS (Edge TTS) → tách vocals (Demucs) → ghép lại (FFmpeg). Giao diện web hiện đại, hỗ trợ chạy dưới dạng web local, Docker, và ứng dụng desktop native (Windows/macOS).

---

## 📥 Tải xuống Desktop

Phiên bản mới nhất: **<!-- LATEST_VERSION -->** — [xem chi tiết & changelog](<!-- LATEST_RELEASE_URL -->)

| Nền tảng | Tải xuống | Yêu cầu |
|----------|-----------|---------|
| 🪟 **Windows** | [VideoDub-windows.zip](<!-- LATEST_RELEASE_URL -->/download/VideoDub-windows.zip) | Windows 10/11 + WebView2 Runtime (có sẵn) |
| 🍎 **macOS** | [VideoDub-macos.zip](<!-- LATEST_RELEASE_URL -->/download/VideoDub-macos.zip) | macOS 12+ (Monterey), chưa notarize |

> **Cài nhanh**:
> - **Windows**: giải nén → double-click `VideoDub.exe` → xong.
> - **macOS**: giải nén → chuột phải `VideoDub.app` → **Open** (lần đầu để vượt Gatekeeper) → kéo vào Applications.

> Các marker `<!-- LATEST_VERSION -->` và `<!-- LATEST_RELEASE_URL -->` được CI tự động cập nhật khi push tag `v*`. Nếu link chưa có, vào tab [Releases](../../releases) để tải thủ công.

---

## 🎯 Tính năng chính

| Tính năng | Công nghệ | Chi tiết |
|-----------|-----------|----------|
| **Tải video** | yt-dlp | YouTube, TikTok, Facebook, Instagram, Twitter, Bilibili, Douyin, Xiaohongshu, Vimeo, Twitch |
| **Nhận diện giọng nói** | faster-whisper | 99+ ngôn ngữ, chạy local, miễn phí |
| **Dịch thuật** | Google Translate (mặc định) + AI tùy chọn | OpenAI, OpenRouter, NVIDIA NIM, Gemini, Anthropic, endpoint OpenAI-compatible |
| **Text-to-Speech** | Edge TTS + gTTS fallback | 20+ giọng, miễn phí |
| **Tách vocals** | Demucs | Chạy local, miễn phí |
| **Xử lý video** | FFmpeg | Ghép video, burn subtitle, blur vùng phụ đề gốc |
| **Quản lý lịch sử** | SQLite | Xem lại, tải lại, xóa hàng loạt |
| **UI** | React + Tailwind | Dark theme, glassmorphism |

---

## 🚀 Cài đặt nhanh (Quick Start)

Chọn một trong 4 cách chạy dưới đây:

| Cách chạy | Phù hợp cho | Lệnh |
|-----------|-------------|------|
| **🐳 Docker Production** | Triển khai server, không muốn cài toolchain | [`docker-run.bat`](#-docker-production) |
| **🐳 Docker Development** | Phát triển, cần hot reload | [`docker-run-dev.bat`](#-docker-development) |
| **💻 Local Development** | Phát triển, muốn toàn quyền kiểm soát | [`run.bat`](#-local-development-windows) |
| **🖥 Desktop App (Windows)** | Người dùng cuối, chạy native, portable | [`desktop/build.bat`](#-desktop-windows) |
| **🍎 Desktop App (macOS)** | Người dùng Mac, chạy native | [`desktop/build_macos.sh`](#-desktop-macos) |

> **Khuyến nghị**: Nếu mới bắt đầu, hãy dùng **Docker Production** — chỉ cần Docker Desktop, không cài Python/Node/FFmpeg.

---

## 🐳 Docker Production (Khuyên dùng)

**Yêu cầu**: Docker Desktop (Windows/Mac) hoặc Docker Engine + Compose v2 (Linux)

```bash
# 1. Clone repo
git clone <repo-url>
cd videodub

# 2. Chạy production
docker-run.bat
```

**Truy cập**:
- Frontend: <http://localhost:3000>
- Backend API: <http://localhost:8000>
- API Docs (Swagger): <http://localhost:8000/docs>
- Health Check: <http://localhost:8000/api/health>

**Dừng**: `docker-stop.bat` hoặc `docker-compose down`

---

## 🐳 Docker Development (Hot Reload)

**Yêu cầu**: Docker Desktop + Compose v2

```bash
cd videodub
docker-run-dev.bat
```

**Truy cập**:
- Frontend (Vite): <http://localhost:5173> (hot reload)
- Backend (FastAPI + reload): <http://localhost:8000>

**Dừng**: `docker-compose -f docker-compose.dev.yml down`

---

## 💻 Local Development (Windows)

**Yêu cầu**:
- Python 3.11+
- Node.js 18+
- FFmpeg (thêm vào PATH: `winget install ffmpeg`)
- GPU (khuyên dùng cho faster-whisper & Demucs)

```bash
cd videodub

# Cài đặt & chạy cùng lúc
run.bat
```

**Truy cập**:
- Frontend: <http://localhost:5173>
- Backend: <http://localhost:8000>

Script `run.bat` tự động:
1. Tạo virtualenv `backend/.venv`
2. Cài Python deps từ `requirements.txt`
3. Cài Node deps & build frontend
4. Khởi động 2 cửa sổ terminal riêng biệt cho backend & frontend

**Chạy riêng lẻ**:
```bash
# Terminal 1 - Backend
cd backend && run.bat

# Terminal 2 - Frontend
cd frontend && run.bat
```

---

## 🖥 Desktop App — Windows (Portable)

**Yêu cầu**:
- Windows 10/11
- Python 3.11+, Node.js 20+
- FFmpeg trong PATH
- WebView2 Runtime (có sẵn trên Win 10/11)

```bash
cd videodub
desktop\build.bat
```

**Kết quả**: `desktop/dist/VideoDub/VideoDub.exe` — file portable, chạy ngay, không cần cài đặt.

**Chạy**:
```bat
desktop\run_desktop.bat
# Hoặc double-click VideoDub.exe
```

**Dữ liệu người dùng**: `%LOCALAPPDATA%\VideoDub\` (database, cookies, video tạm, kết quả)

📖 Xem chi tiết: [`videodub/desktop/README.md`](videodub/desktop/README.md)

---

## 🍎 Desktop App — macOS (Native .app)

**Yêu cầu**:
- macOS 12+ (Monterey)
- Python 3.11+ (Homebrew)
- Node.js 20+ (`brew install node`)
- Xcode Command Line Tools: `xcode-select --install`
- Homebrew

```bash
cd videodub
chmod +x desktop/build_macos.sh
./desktop/build_macos.sh
```

**Kết quả**: `desktop/dist/VideoDub.app` — bundle macOS native.

**Chạy**:
```bash
open desktop/dist/VideoDub.app
# Hoặc
./desktop/run_macos.sh
```

> **Lưu ý**: Lần đầu chạy, chuột phải → **Open** để vượt Gatekeeper (unsigned ad-hoc).

**Dữ liệu người dùng**: `~/.local/share/VideoDub/`

📖 Xem chi tiết: [`videodub/desktop/README_desktop_macos.md`](videodub/desktop/README_desktop_macos.md)

---

## 📦 Các script tiện ích

Tất cả script nằm tại thư mục gốc `videodub/`:

| Script | Mô tả |
|--------|-------|
| `build.bat` | Build frontend production + cài backend deps |
| `run.bat` | Chạy cả 2 dev server (backend + frontend) |
| `docker-run.bat` | Build & chạy Docker production |
| `docker-run-dev.bat` | Build & chạy Docker development (hot reload) |
| `docker-stop.bat` | Dừng tất cả container Docker |
| `stop-local.bat` | Dừng dev server local trên port 8000 & 5173 |
| `desktop/build.bat` | Build Windows desktop app |
| `desktop/run_desktop.bat` | Chạy Windows desktop app |
| `desktop/build_macos.sh` | Build macOS .app bundle |
| `desktop/run_macos.sh` | Chạy macOS app |

---

## 🌐 Địa chỉ truy cập

| Môi trường | Frontend | Backend API | API Docs |
|------------|----------|-------------|----------|
| Local Dev | http://localhost:5173 | http://localhost:8000 | http://localhost:8000/docs |
| Docker Prod | http://localhost:3000 | http://localhost:8000 | http://localhost:8000/docs |
| Docker Dev | http://localhost:5173 | http://localhost:8000 | http://localhost:8000/docs |

---

## ⚙️ Cấu hình AI Translation (Tùy chọn)

Mặc định dùng **Google Translate (miễn phí, không cần key)**. Để bật dịch AI chất lượng cao:

1. Mở app → **Cài đặt** → **Dịch thuật**
2. Chọn **Provider**: OpenAI / OpenRouter / NVIDIA NIM / Google Gemini / Anthropic / OpenAI-compatible
3. Nhập **API Key** → **Kiểm tra kết nối** → **Lưu**
4. Key được lưu local, không bao giờ gửi ra ngoài qua API settings

Nếu thiếu key hoặc AI lỗi → tự động fallback sang Google Translate cho block đó.

---

## 📁 Cấu trúc thư mục chính

```
videodub/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # Routes: dubbing, history, settings, cookies
│   │   ├── core/        # Pipeline, downloader, paths
│   │   ├── models/      # SQLAlchemy models
│   │   └── schemas/     # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # React + Vite + Tailwind
│   ├── src/
│   │   ├── pages/       # Dashboard, Dubbing, History, Settings
│   │   ├── components/  # UI components
│   │   ├── stores/      # Zustand state
│   │   └── lib/         # API, utils, workflow
│   ├── Dockerfile / Dockerfile.dev
│   └── package.json
├── desktop/              # Desktop packaging
│   ├── build.bat         # Windows build
│   ├── run_desktop.bat   # Windows run
│   ├── build_macos.sh    # macOS build
│   ├── run_macos.sh      # macOS run
│   ├── README.md         # Windows docs
│   └── README_desktop_macos.md  # macOS docs
├── docker-compose.yml          # Production
├── docker-compose.dev.yml      # Development
├── build.bat / run.bat         # Local dev
├── docker-run.bat / docker-run-dev.bat / docker-stop.bat
└── README.md                   # (File này)
```

---

## 🐛 Troubleshooting nhanh

| Vấn đề | Giải pháp |
|--------|-----------|
| **Port conflict** | Đổi port trong `docker-compose.yml` hoặc `frontend/vite.config.ts` |
| **FFmpeg not found** | Win: `winget install ffmpeg` · Mac: `brew install ffmpeg` · Linux: `apt install ffmpeg` |
| **YouTube download fail** | Cập nhật yt-dlp: `pip install -U yt-dlp` · Thêm cookies YouTube ở Settings |
| **GPU OOM / chậm** | Dùng Whisper model nhỏ hơn (tiny/base) · Bật GPU trong Docker compose |
| **Docker build fail** | `docker-compose down -v && docker system prune -a && docker-run.bat` |
| **Desktop app crash** | Xem log: Windows → Event Viewer · macOS → Console.app |

---

## 📚 Tài liệu chi tiết

| Tài liệu | Link |
|----------|------|
| Hướng dẫn cài đặt đầy đủ (Local/Docker) | [`videodub/README.md`](videodub/README.md) |
| Desktop Windows — Build & Run | [`videodub/desktop/README.md`](videodub/desktop/README.md) |
| Desktop macOS — Build & Run | [`videodub/desktop/README_desktop_macos.md`](videodub/desktop/README_desktop_macos.md) |
| API Documentation (Swagger) | Chạy app → <http://localhost:8000/docs> |

---

## 🤝 Đóng góp

1. Fork repo
2. Tạo branch: `git checkout -b feature/ten-tinh-nang`
3. Commit: `git commit -m "feat: mô tả thay đổi"`
4. Push: `git push origin feature/ten-tinh-nang`
5. Tạo Pull Request

---

## 📄 License

**MIT License** — Tự do sử dụng cá nhân và thương mại.

---

## ⭐ Hỗ trợ dự án

Nếu VideoDub hữu ích cho bạn, hãy cho một ⭐ trên GitHub để ủng hộ dự án!