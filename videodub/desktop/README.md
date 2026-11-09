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

## License (bán cho khách hàng)

Bản đóng gói (EXE/.app) luôn yêu cầu license: lần mở đầu tiên hiện màn hình
**Kích hoạt VideoDub**. Mỗi mã chỉ dùng trên **một thiết bị**; app xác thực online
định kỳ (6 giờ/lần khi đang mở) và được dùng ngoại tuyến tối đa **72 giờ** sau
lần xác thực thành công gần nhất (không vượt quá hạn license). Khi chưa có license
hợp lệ, backend từ chối `/api/dubbing/preview`, `/start`, `/{id}/retry`; lịch sử
và tải kết quả cũ vẫn dùng được. `run.bat` (chạy từ mã nguồn) không bị khóa; đặt
`VIDEODUB_LICENSE_REQUIRED=1` + `VIDEODUB_LICENSE_CONFIG=<file json>` để thử.

Nhà cung cấp: [Keygen](https://keygen.sh) (cloud, hoặc tự host Keygen CE). Code
nằm sau adapter (`backend/app/core/license_keygen.py`, giao diện `LicenseProvider`
trong `licensing.py`) nên có thể thay máy chủ khác. App chỉ chứa **khóa công khai**
Ed25519 để kiểm tra chứng nhận (machine file) — không có token quản trị nào.

### Thiết lập một lần

1. Tạo tài khoản Keygen, tạo **Product** "VideoDub" và một **Policy**:
   - `maxMachines = 1`, `strict = true`, `floating = false`
   - `authenticationStrategy = LICENSE` (app kích hoạt máy bằng chính mã license)
   - `requireFingerprintScope = true`, `expirationStrategy` tùy ý (vd. `RESTRICT_ACCESS`)
   - Đặt `duration` nếu bán theo thời hạn (để trống = vĩnh viễn).
2. Lấy **Account ID** và **Ed25519 public key** (Settings → Public keys, 64 ký tự hex).
3. Khai báo cho build (là giá trị công khai, dùng *Repository variables* chứ không
   phải secrets): `VIDEODUB_LICENSE_ACCOUNT`, `VIDEODUB_LICENSE_PUBLIC_KEY`,
   `VIDEODUB_LICENSE_API_URL` (bỏ trống = `https://api.keygen.sh`; điền URL Keygen CE
   nếu tự host) và `VIDEODUB_LICENSE_CONTACT` (vd. "Liên hệ Zalo 09xx để được hỗ trợ.").
   Build local: `set VIDEODUB_LICENSE_ACCOUNT=...` trước `desktopuild.bat`.
   **Thiếu/sai các biến này thì build dừng lại** để không lọt bản không có license.

### Cấp mã cho khách

1. Keygen dashboard → Licenses → **New license**, chọn policy VideoDub, ghi tên/email
   khách vào `name`/metadata. (Hoặc tự động: webhook thanh toán gọi
   `POST /v1/accounts/<acct>/licenses` bằng admin token **trên máy chủ của bạn**.)
2. Gửi khách **license key** cùng file cài đặt. Khách mở app, dán mã, bấm *Kích hoạt*
   (cần mạng lần đầu).
3. Đổi máy: vào license → Machines → xóa thiết bị cũ, khách kích hoạt lại trên máy mới.
   Khóa/gia hạn: Suspend/Renew license; app trên máy khách nhận thay đổi ở lần xác
   thực online kế tiếp (máy offline có thể dùng nốt tối đa 72 giờ còn lại).

Lưu ý: license chống chia sẻ thông thường, không chống được người sửa mã chương trình.
Cài lại Windows/macOS đổi mã thiết bị → cần xóa thiết bị cũ trong Keygen như đổi máy.
Trạng thái license của khách lưu tại `<thư mục dữ liệu>/license.json`.

## Ghi chú

- Model Whisper và model Demucs được tải/cache ở lần sử dụng đầu tiên; chúng không được nhúng vào file executable để tránh làm gói phát hành quá lớn.
- Nếu máy không có WebView2 Runtime, cài Microsoft Edge WebView2 Runtime rồi chạy lại.
- Bản `onedir` được chọn thay cho `onefile` vì PyTorch/Demucs/Whisper có nhiều DLL lớn và khởi động ổn định hơn trong cấu trúc thư mục.
- Backend development vẫn chạy như cũ bằng `run.bat`; thay đổi phục vụ frontend production chỉ được bật khi thư mục build tồn tại hoặc launcher đặt `VIDEODUB_FRONTEND_DIR`.
