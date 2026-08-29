# VideoDub Desktop (macOS)

Bản desktop dùng `pywebview` với CocoaWebKit (WebKit tích hợp sẵn macOS) để mở giao diện React production trong cửa sổ native. FastAPI chạy trên loopback port ngẫu nhiên và tự phục vụ frontend — không cần mở hai terminal hay Docker.

## Yêu cầu build

- macOS 12 (Monterey) trở lên
- Python 3.11+
- Node.js 20+ (qua Homebrew)
- Xcode Command Line Tools (`xcode-select --install`) — cần cho `iconutil` tạo `.icns`
- Homebrew (`brew`) — cài Node.js, FFmpeg

## Build

Chạy từ thư mục `videodub`:

```bash
chmod +x desktop/build_macos.sh
./desktop/build_macos.sh
```

Script sẽ:

1. Tạo/tái sử dụng `backend/.venv`.
2. Cài Node.js qua Homebrew nếu chưa có.
3. Build `frontend/dist`.
4. Cài dependency backend và desktop.
5. Cài FFmpeg qua Homebrew (`brew install ffmpeg`) và copy `ffmpeg` + `ffprobe` vào gói.
6. Tạo icon `VideoDub.ico` (Windows) và `VideoDub.icns` (macOS).
7. Tạo bản portable tại `desktop/dist/VideoDub.app`.

## Chạy

```bash
open desktop/dist/VideoDub.app
# hoặc
./desktop/run_macos.sh
```

## Dịch AI tùy chọn

Trong **Cài đặt → Dịch thuật**, có thể nhập API key cho OpenAI, OpenRouter, NVIDIA NIM, Google Gemini, Anthropic hoặc endpoint tương thích OpenAI. Key được lưu trong dữ liệu cục bộ của ứng dụng và chỉ hiển thị bốn ký tự cuối. Nếu không có key hoặc dịch AI gặp lỗi, VideoDub tự động dùng Google Translate cho block phụ đề đó và không làm hỏng cả job.

## Dữ liệu người dùng

Bản đóng gói ghi database, cookies, video tạm và kết quả vào:

```text
~/.local/share/VideoDub/
```

Các thư mục chính: `output`, `temp`, `cookies`, `logs`; database là `videodub.db`. Dữ liệu không bị ghi vào thư mục ứng dụng (`.app`).

## Ghi chú

- Model Whisper và model Demucs được tải/cache ở lần sử dụng đầu tiên; chúng không được nhúng vào file executable để tránh làm gói phát hành quá lớn.
- Bản `onedir` (thư mục `.app`) được chọn thay cho `onefile` vì PyTorch/Demucs/Whisper có nhiều dylib lớn và khởi động ổn định hơn trong cấu trúc bundle macOS.
- Backend development vẫn chạy như cũ bằng `run.bat` / `run.sh`; thay đổi phục vụ frontend production chỉ được bật khi thư mục build tồn tại hoặc launcher đặt `VIDEODUB_FRONTEND_DIR`.
- Nếu muốn phân phối cho người khác: cần Apple Developer certificate + notarization. Bản internal dùng `ad-hoc signing` (Right-click → Open để vượt Gatekeeper lần đầu).

## Troubleshooting

| Lỗi | Nguyên nhân / Giải pháp |
|-----|-------------------------|
| `iconutil not found` | Cài Xcode Command Line Tools: `xcode-select --install` |
| `ffmpeg not found` | `brew install ffmpeg` rồi build lại |
| `ModuleNotFoundError: webview` | `./desktop/build_macos.sh` tự cài; nếu chạy tay: `backend/.venv/bin/pip install -r desktop/requirements.txt` |
| App không mở / crash ngay | Mở Console.app (`/Applications/Utilities/Console.app`), lọc "VideoDub" xem log |