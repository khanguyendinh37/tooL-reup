# VideoDub - Video Dubbing Tool

Ứng dụng lồng tiếng video tự động bằng AI - **100% MIỄN PHÍ**, chạy local.

## 🚀 Quick Start

### Option 1: Docker Production (Recommended)
```bash
docker-run.bat
```
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Option 2: Docker Development (Hot Reload)
```bash
docker-run-dev.bat
```
- Frontend (Vite): http://localhost:5173
- Backend (FastAPI + reload): http://localhost:8000

### Option 3: Local Development (No Docker)
```bash
# Build both
build.bat

# Run both
run.bat
```

### Option 4: Desktop Windows (Portable)
```bat
desktop\build.bat
desktop\run_desktop.bat
```

The desktop build opens the React UI in a native window, starts FastAPI locally, bundles FFmpeg, and stores user data in `%LOCALAPPDATA%\VideoDub`. Windows local development now uses the same data directory by default, so settings/API keys are consistent between `run.bat` and desktop. See [`desktop/README.md`](desktop/README.md) for requirements and troubleshooting.

Or run separately:
```bash
# Terminal 1 - Backend
cd backend
run.bat

# Terminal 2 - Frontend
cd frontend
run.bat
```

## 📋 Available Scripts

| Script | Description |
|--------|-------------|
| `build.bat` | Build both frontend & backend locally |
| `run.bat` | Start both dev servers locally |
| `docker-run.bat` | Build & run production Docker containers |
| `docker-run-dev.bat` | Build & run development Docker containers (hot reload) |
| `docker-stop.bat` | Stop all Docker containers |
| `desktop\build.bat` | Build portable Windows desktop app |
| `desktop\run_desktop.bat` | Launch the packaged desktop app |
| `stop-local.bat` | Stop local development servers on ports 8000 and 5173 |

### Backend Scripts (`backend/`)
| Script | Description |
|--------|-------------|
| `build.bat` | Install Python dependencies |
| `run.bat` | Start FastAPI dev server (port 8000) |

### Frontend Scripts (`frontend/`)
| Script | Description |
|--------|-------------|
| `build.bat` | Install deps & build for production |
| `run.bat` | Start Vite dev server (port 5173) |

## 🐳 Docker Commands (Manual)

```bash
# Production
docker-compose up -d --build      # Build & start
docker-compose down               # Stop
docker-compose down -v            # Stop & remove volumes (DB data)
docker-compose logs -f            # View logs
docker-compose ps                 # Check status

# Development
docker-compose -f docker-compose.dev.yml up -d --build
docker-compose -f docker-compose.dev.yml down
docker-compose -f docker-compose.dev.yml logs -f
```

## 🔧 Requirements

### Local Development
- **Python 3.11+**
- **Node.js 18+**
- **FFmpeg** (for video/audio processing)
- **GPU** (recommended for faster-whisper & Demucs)

### Docker
- **Docker Desktop** (Windows/Mac) or Docker Engine (Linux)
- **Docker Compose v2+**

## 📁 Project Structure

```
videodub/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Pipeline processing
│   │   ├── models/         # Database models
│   │   └── schemas/        # Pydantic schemas
│   ├── Dockerfile          # Production Dockerfile
│   ├── requirements.txt
│   └── build.bat / run.bat
├── frontend/               # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── pages/          # Dashboard, Dubbing, History, Settings
│   │   ├── stores/         # Zustand state management
│   │   └── lib/            # Utilities, API
│   ├── Dockerfile          # Production (nginx)
│   ├── Dockerfile.dev      # Development
│   ├── nginx.conf
│   ├── package.json
│   └── build.bat / run.bat
├── docker-compose.yml      # Production
├── docker-compose.dev.yml  # Development
├── build.bat               # Build both locally
├── run.bat                 # Run both locally
├── docker-run.bat          # Docker production
├── docker-run-dev.bat      # Docker development
├── docker-stop.bat         # Stop containers
└── README.md
```

## 🌐 Access Points

| Service | Local | Docker (Prod) | Docker (Dev) |
|---------|-------|---------------|--------------|
| Frontend | http://localhost:5173 | http://localhost:3000 | http://localhost:5173 |
| Backend API | http://localhost:8000 | http://localhost:8000 | http://localhost:8000 |
| API Docs | http://localhost:8000/docs | http://localhost:8000/docs | http://localhost:8000/docs |
| Health Check | http://localhost:8000/api/health | http://localhost:8000/api/health | http://localhost:8000/api/health |

## 🛠 Features

- **Video Download**: YouTube, TikTok, Facebook, Twitter + 1000+ sites (yt-dlp)
- **Subtitle Generation**: faster-whisper (local, free, 99+ languages)
- **Translation**: Google Translate fallback plus optional OpenAI, OpenRouter, NVIDIA NIM, Gemini, Anthropic, and OpenAI-compatible endpoints
- **Text-to-Speech**: Edge TTS (free, 300+ voices) + gTTS fallback
- **Vocal Removal**: Demucs (local, free)
- **Video Processing**: FFmpeg for merging
- **History Management**: SQLite database
- **Dark Theme UI**: Glassmorphism design
- **Speed Control**: 0.5x - 2x speech rate
- **Cookies Support**: For private/restricted content

## ⚙️ Configuration

### AI Translation (optional)
Open **Cài đặt → Dịch thuật** to configure an AI provider:

- OpenAI, OpenRouter, NVIDIA NIM, Google Gemini, Anthropic, or any OpenAI-compatible endpoint.
- Enter an API key and select a model. The key is stored locally and is never returned by the settings API.
- When a key is missing, the configuration is incomplete, or an AI request fails, the app automatically keeps the affected subtitle block on Google Translate instead of failing the dubbing job.
- The **Kiểm tra kết nối** action checks the selected route without saving the key; save the settings after a successful test to use AI for future jobs.

### Backend Environment
Create `backend/.env`:
```env
DATABASE_URL=sqlite+aiosqlite:///./data/videodub.db
# Optional: Add API keys for premium services
```

### GPU Support (Docker)
Uncomment in `docker-compose.yml`:
```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```
Requires: [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## 🐛 Troubleshooting

### Docker Issues
```bash
# Full reset
docker-compose down -v
docker system prune -a
docker-run.bat
```

### Port Conflicts
Default ports:
- Frontend (local): 5173
- Backend (local): 8000
- Frontend (Docker prod): 3000
- Backend (Docker): 8000

Change in `docker-compose.yml` or `frontend/vite.config.ts` if needed.

### Backend Dependencies
```bash
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

### Frontend Dependencies
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### FFmpeg Not Found
- Windows: `winget install ffmpeg` or download from ffmpeg.org
- Mac: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

### YouTube Download Fails
- Update yt-dlp: `pip install -U yt-dlp`
- Add YouTube cookies in Settings page

### GPU / OOM Errors
- Use smaller Whisper model (tiny/base instead of small/medium)
- Enable CPU-only mode (default in Docker)

### Slow Processing
- Use smaller Whisper model
- Enable GPU if available

## 📝 License

MIT License - Free for personal and commercial use.