# VideoDub - Tool Lồng Tiếng Video

Ứng dụng lồng tiếng video tự động bằng AI - **100% MIỄN PHÍ**, chạy local.

## Tính năng

- **Tải video** từ YouTube, TikTok, Facebook, Twitter và 1000+ nền tảng
- **Tạo phụ đề SRT** bằng faster-whisper (chạy local, miễn phí)
- **Dịch thuật** bằng Google Translate (miễn phí, không cần API key)
- **Tạo giọng lồng tiếng** bằng Google TTS (gTTS, miễn phí)
- **Xóa giọng gốc** bằng Demucs (chạy local, miễn phí)
- **Ghép video** tự động với ffmpeg
- **Quản lý lịch sử** - xem lại, tải lại, xóa video đã lồng tiếng
- **Giao diện đẹp mắt** với Dark theme + Glassmorphism
- **Điều chỉnh tốc độ giọng nói** (0.5x - 2x)
- **Hỗ trợ cookies** cho các nền tảng cần đăng nhập

## Cài đặt

### Yêu cầu

- Python 3.11+
- Node.js 18+
- ffmpeg (cài đặt trước)
- GPU (khuyến nghị cho faster-whisper và demucs)

### Bước 1: Clone và cài đặt

```bash
cd videodub

# Cài Backend
cd backend
pip install -r requirements.txt

# Cài Frontend
cd ../frontend
npm install
```

### Bước 2: Chạy ứng dụng

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
chmod +x run.sh
./run.sh
```

**Hoặc chạy riêng:**

```bash
# Terminal 1 - Backend
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

### Bước 3: Truy cập

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Docker

### Cài đặt Docker

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) cho Windows/Mac
- Docker Engine cho Linux

### Chạy với Docker (Production)

**Windows:**
```bash
docker-run.bat
```

**Linux/Mac:**
```bash
chmod +x docker-run.sh
./docker-run.sh
```

**Hoặc dùng docker-compose trực tiếp:**
```bash
# Build và chạy
docker-compose up -d

# Xem log
docker-compose logs -f

# Dừng
docker-compose down
```

### Chạy Development mode với Docker

```bash
# Linux/Mac
chmod +x docker-run-dev.sh
./docker-run-dev.sh

# Windows
docker-run-dev.bat
```

Hoặc trực tiếp:
```bash
docker-compose -f docker-compose.dev.yml up -d
```

Frontend dev server: http://localhost:5173

### Truy cập (Docker Production)

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### GPU Support (Optional)

Để sử dụng GPU với Docker, cần cài đặt [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) và uncomment phần `deploy.resources.reservations.devices` trong `docker-compose.yml`.

## Cấu trúc thư mục

```
videodub/
├── frontend/               # React + Vite + Tailwind
│   ├── src/
│   │   ├── components/     # UI components
│   │   ├── pages/          # Trang Dashboard, Dubbing, History, Settings
│   │   ├── stores/         # Zustand state management
│   │   └── lib/            # Utilities, API
│   ├── Dockerfile          # Production build
│   ├── Dockerfile.dev      # Development build
│   └── package.json
│
├── backend/                # Python FastAPI
│   ├── app/
│   │   ├── api/            # API endpoints
│   │   ├── core/           # Pipeline processing
│   │   ├── models/         # Database models
│   │   └── schemas/        # Pydantic schemas
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml      # Production Docker
├── docker-compose.dev.yml  # Development Docker
├── docker-run.sh           # Script chạy Docker (Linux/Mac)
├── docker-run.bat          # Script chạy Docker (Windows)
├── docker-run-dev.sh       # Script chạy Docker Dev (Linux/Mac)
├── docker-run-dev.bat      # Script chạy Docker Dev (Windows)
├── run.bat                 # Script chạy local (Windows)
├── run.sh                  # Script chạy local (Linux/Mac)
└── README.md
```

## Công nghệ sử dụng

| Thành phần | Công cụ | Chi phí |
|------------|----------|---------|
| Frontend | React + Vite + Tailwind | Miễn phí |
| Backend | Python FastAPI | Miễn phí |
| Database | SQLite | Miễn phí |
| Download | yt-dlp | Miễn phí |
| Speech-to-Text | faster-whisper | Miễn phí |
| Translation | deep-translator (Google) | Miễn phí |
| TTS | gTTS (Google Translate TTS) | Miễn phí |
| Vocal Remove | demucs | Miễn phí |
| Video Processing | ffmpeg | Miễn phí |

## Hỗ trợ ngôn ngữ

- **Nhận dạng:** 99+ ngôn ngữ (qua Whisper)
- **Dịch thuật:** 16+ ngôn ngữ
- **Lồng tiếng:** 300+ giọng (qua Edge TTS - cần kết nối internet)

## Các nút lệnh hữu ích

```bash
# Build lại Docker images
docker-compose build

# Xem log real-time
docker-compose logs -f

# Dừng và xóa containers
docker-compose down

# Dừng và xóa containers + volumes (xóa data)
docker-compose down -v

# Chạy lại mà không build
docker-compose up -d
```

## Cấu hình Cookies (cho YouTube, Facebook, etc.)

Một số nền tảng yêu cầu đăng nhập để tải video. Bạn có thể:

1. Vào trang **Settings** (Cài đặt) trong ứng dụng
2. Chọn nền tảng (YouTube, Facebook, etc.)
3. Upload file cookies.txt (export từ trình duyệt bằng extension "Get cookies.txt LOCALLY")

## Xử lý sự cố

### Lỗi "ffmpeg not found"
Cài đặt ffmpeg:
- Windows: `winget install ffmpeg` hoặc tải từ ffmpeg.org
- Mac: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

### Lỗi tải video YouTube
- Cập nhật yt-dlp: `pip install -U yt-dlp`
- Thêm cookies YouTube trong Settings

### Lỗi GPU/Out of memory
- Giảm Whisper model size (tiny, base thay vì small/medium)
- Sử dụng CPU-only mode (mặc định trong Docker)

### Tốc độ xử lý chậm
- Sử dụng Whisper model nhỏ hơn (tiny/base)
- Bật GPU nếu có (cần nvidia-container-toolkit cho Docker)

## License

MIT License