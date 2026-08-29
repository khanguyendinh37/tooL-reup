# VideoDub Desktop

**Platform support:** [Windows](#windows-build) | [macOS](README_desktop_macos.md)

Bản desktop dùng `pywebview` để mở giao diện React production trong cửa sổ native. FastAPI chạy trên loopback port ngẫu nhiên và tự phục vụ frontend, vì vậy không cần mở hai terminal hoặc chạy Docker.

## Windows Build

### Yêu cầu

- Windows 10/11
- Python 3.11+
- Node.js 20+
- FFmpeg có `ffmpeg.exe` và `ffprobe.exe` trong `PATH`
- WebView2 Runtime (thường đã có trên Windows 10/11)

## Build

Chạy từ thư mục `videodub`:

```bat
desktop\build.bat
```

Script sẽ:

1. Tạo/tái sử dụng `backend\.venv`.
2. Build `frontend\dist`.
3. Cài dependency backend và desktop.
4. Sao chép FFmpeg vào gói để bản desktop không phụ thuộc PATH sau khi build.
5. Tạo bản portable tại `desktop\dist\VideoDub\VideoDub.exe`.

## Chạy

```bat
desktop\run_desktop.bat
```

Hoặc mở trực tiếp `desktop\dist\VideoDub\VideoDub.exe`.

## Dịch AI tùy chọn

Trong **Cài đặt → Dịch thuật**, có thể nhập API key cho OpenAI, OpenRouter, NVIDIA NIM, Google Gemini, Anthropic hoặc endpoint tương thích OpenAI. Key được lưu trong dữ liệu cục bộ của ứng dụng và chỉ hiển thị bốn ký tự cuối. Nếu không có key hoặc dịch AI gặp lỗi, VideoDub tự động dùng Google Translate cho block phụ đề đó và không làm hỏng cả job.


## Dữ liệu người dùng

Bản đóng gói ghi database, cookies, video tạm và kết quả vào:

```text
%LOCALAPPDATA%\VideoDub\
```

Các thư mục chính là `output`, `temp`, `cookies`, `logs`; database là `videodub.db`. Dữ liệu không bị ghi vào `Program Files` hoặc thư mục cài đặt. Trên Windows, `run.bat` dùng cùng thư mục này mặc định để cấu hình không bị tách giữa web và desktop.

## Ghi chú

- Model Whisper và model Demucs được tải/cache ở lần sử dụng đầu tiên; chúng không được nhúng vào file executable để tránh làm gói phát hành quá lớn.
- Nếu máy không có WebView2 Runtime, cài Microsoft Edge WebView2 Runtime rồi chạy lại.
- Bản `onedir` được chọn thay cho `onefile` vì PyTorch/Demucs/Whisper có nhiều DLL lớn và khởi động ổn định hơn trong cấu trúc thư mục.
- Backend development vẫn chạy như cũ bằng `run.bat`; thay đổi phục vụ frontend production chỉ được bật khi thư mục build tồn tại hoặc launcher đặt `VIDEODUB_FRONTEND_DIR`.
