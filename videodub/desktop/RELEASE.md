# Phát hành VideoDub cho khách hàng

Tài liệu này dành cho người bán / người phát hành. Khách hàng chỉ cần file cài đặt.

## Kết quả mỗi lần phát hành

| File | Dành cho | Ghi chú |
|------|----------|---------|
| `VideoDub-Setup-<x.y.z>.exe` | Windows 10/11 64-bit | Bộ cài chính. Cài theo user, không hỏi quyền admin, tự cài WebView2, tạo shortcut, có gỡ cài đặt trong Settings → Apps |
| `VideoDub-<x.y.z>-windows-portable.zip` | Windows | Bản giải nén chạy luôn, cho khách không được phép cài phần mềm |
| `VideoDub-<x.y.z>-macos-arm64.dmg` | Mac chip Apple (M1 trở lên) | Kéo-thả vào Applications |

**Mac Intel không được hỗ trợ**: PyTorch đã ngừng phát hành bản macOS x86_64 từ 2.3, trong khi dự án dùng `torch==2.13`.

Dữ liệu của khách (job, video, cài đặt) nằm ngoài thư mục cài đặt (`%LOCALAPPDATA%\VideoDub`, `~/.local/share/VideoDub`), nên cập nhật hoặc gỡ cài đặt không làm mất dữ liệu.

## Phát hành một phiên bản

1. Commit toàn bộ thay đổi lên nhánh chính.
2. Tạo và push tag (số phiên bản tăng dần, dạng `vMAJOR.MINOR.PATCH`):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
3. Vào tab **Actions** trên GitHub, đợi workflow **Build Release** chạy xong (khoảng 40–90 phút; notarize Mac có thể lâu hơn).
4. Các file nằm trong **Releases → v1.0.0**. Tải về, cài thử trên một máy sạch rồi mới giao cho khách.

Có thể chạy lại bằng tay: Actions → Build Release → **Run workflow**, nhập phiên bản (ví dụ `1.0.1`).

> ⚠️ **Repo public = ai cũng tải được miễn phí.** Nếu bán, hãy để repo **private** (Release của repo private chỉ người có quyền mới tải được), rồi giao file cho khách qua nền tảng bán hàng (Lemon Squeezy, Gumroad, Google Drive riêng, …) kèm license key.

## Ký số (để khách không bị cảnh báo bảo mật)

Workflow vẫn build bình thường khi chưa có chứng chỉ, nhưng:
- Windows: SmartScreen hiện "Windows protected your PC" → khách phải bấm *More info → Run anyway*; antivirus dễ báo nhầm.
- macOS: khách phải vào System Settings → Privacy & Security → *Open Anyway* (macOS 15 không còn cho mở bằng chuột phải → Open).

Ký số chỉ bật khi đã thêm các secret dưới đây vào **GitHub → Settings → Secrets and variables → Actions**.

### Windows — Azure Artifact Signing (khoảng 10 USD/tháng)

1. Tạo tài khoản Azure, tạo resource **Artifact Signing** (trước đây là *Trusted Signing*), hoàn tất xác minh danh tính (cá nhân hoặc doanh nghiệp; kiểm tra quốc gia của bạn có được hỗ trợ không).
2. Tạo **Certificate profile** loại *Public Trust*.
3. Tạo một App registration (service principal), gán role **Artifact Signing Certificate Profile Signer** trên signing account.
4. Thêm secrets:

| Secret | Giá trị |
|--------|---------|
| `AZURE_TENANT_ID` | Tenant ID |
| `AZURE_CLIENT_ID` | Client ID của app registration |
| `AZURE_CLIENT_SECRET` | Client secret |
| `AZURE_SIGNING_ENDPOINT` | Ví dụ `https://eus.codesigning.azure.net/` (theo region của account) |
| `AZURE_SIGNING_ACCOUNT` | Tên signing account |
| `AZURE_CERTIFICATE_PROFILE` | Tên certificate profile |

Lựa chọn khác: chứng chỉ OV/EV từ Sectigo, SSL.com, DigiCert… (khoảng 200–500 USD/năm). Từ 2023, các chứng chỉ này nằm trên token phần cứng hoặc cloud HSM, nên phải thay bước ký trong workflow bằng công cụ của nhà cung cấp đó.

### macOS — Apple Developer ID + notarize (99 USD/năm)

1. Đăng ký **Apple Developer Program**.
2. Trên máy Mac: Xcode → Settings → Accounts → Manage Certificates → tạo **Developer ID Application**. Mở Keychain Access, export chứng chỉ kèm private key thành file `.p12` (đặt mật khẩu).
3. Tạo *app-specific password* tại https://account.apple.com (Sign-In and Security → App-Specific Passwords).
4. Thêm secrets:

| Secret | Giá trị |
|--------|---------|
| `MACOS_CERTIFICATE` | Nội dung file `.p12` dạng base64: `base64 -i cert.p12 \| pbcopy` |
| `MACOS_CERTIFICATE_PASSWORD` | Mật khẩu của file `.p12` |
| `MACOS_SIGN_IDENTITY` | Ví dụ `Developer ID Application: Nguyen Van A (AB12CD34EF)` |
| `APPLE_ID` | Email Apple ID |
| `APPLE_TEAM_ID` | Team ID 10 ký tự |
| `APPLE_APP_PASSWORD` | App-specific password ở bước 3 |

Tùy chọn: thêm **variable** (không phải secret) `VIDEODUB_PUBLISHER` = tên công ty/cá nhân của bạn; tên này hiện trong thuộc tính file `.exe` và bản quyền của app Mac.

## Build trên máy (không qua GitHub)

Windows (cần Python 3.11, Node.js, FFmpeg trong PATH, Inno Setup 6: `winget install JRSoftware.InnoSetup`):
```bat
cd videodub
set VIDEODUB_VERSION=1.0.0
desktop\build.bat
cd desktop
installer\build_installer.bat 1.0.0
```
Bộ cài nằm ở `videodub/desktop/dist/installer/`.

macOS (Apple Silicon, cần Python 3.11, Homebrew):
```bash
cd videodub
VIDEODUB_VERSION=1.0.0 ./desktop/build_macos.sh
./desktop/macos/package_macos.sh 1.0.0
```
Muốn ký và notarize trên máy, đặt `MACOS_SIGN_IDENTITY`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` trước lệnh cuối.

## Checklist trước khi giao cho khách

- [ ] Cài bộ cài trên một máy Windows sạch (chưa từng chạy dev), mở app, lồng tiếng thử 1 video ngắn.
- [ ] Mở `.dmg` trên một Mac khác, kéo vào Applications, mở app không có cảnh báo (nếu đã notarize).
- [ ] Ghi chú cho khách: lần lồng tiếng đầu tiên cần mạng để tải model (~500 MB); máy không có GPU xử lý video 1 giờ mất khoảng 1–2 giờ; nên có RAM 16 GB cho video dài.
- [ ] Gửi kèm license key (khi đã có cơ chế kích hoạt).
