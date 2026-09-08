# Kiểm chứng web và app

Web và desktop dùng chung `backend/requirements.txt`. Các thư viện tải video,
TTS và xử lý âm thanh chính được cố định phiên bản. Các dependency phụ còn lại
vẫn do pip giải quyết; đây chưa phải lockfile toàn bộ dependency cho mọi OS.
Cả hai cách cài dùng `pip install -r` rồi `pip check`.

Trên Windows, `run.bat` ưu tiên FFmpeg tại `desktop/vendor/ffmpeg` nếu có,
cùng binary được đóng gói vào app. Khi không có, web dùng FFmpeg trong PATH.

## Cổng kiểm tra trước phát hành

Workflow chạy bài kiểm tra bằng Python nguồn và bằng chính executable đã build,
so sánh phiên bản Python, các thư viện xử lý chính, phiên bản FFmpeg/ffprobe,
target giả lập trình duyệt và kết quả tạo video mẫu rồi tách audio.
Bài kiểm tra còn gọi Demucs `--help` qua đúng Python nguồn hoặc worker trong EXE,
để phát hiện bản app vô tình phụ thuộc lệnh `demucs` cài ngoài hệ thống.
Bản Windows còn kiểm tra nạp WinForms/Python.NET. Bất kỳ sai khác hoặc lỗi nào
sẽ chặn bước nén và phát hành. Báo cáo JSON nằm trong Actions artifacts.

Bài này chạy offline, không tải model và không gửi nội dung ra dịch vụ.
Nó không chứng minh rằng Facebook/Douyin/TTS đang hoạt động hoặc cookies còn hạn,
cũng không thay thế kiểm tra giao diện trực quan và thử video thật.

## Đối chiếu video thật

`app.core.pipeline_check` và executable với `--pipeline-check URL DATA_DIR REPORT`
chạy cùng pipeline với tiếng Trung → tiếng Việt, giọng Nam Minh, Whisper small,
phụ đề bật, dịch Google mặc định. Test không sao chép API key hay cấu hình AI
cá nhân. Chỉ dùng thư mục dữ liệu và database mới, riêng cho từng lần thử.
Đặt bản sao cookies hợp lệ vào `DATA_DIR/cookies` trước khi chạy; không commit
cookies hoặc dữ liệu thử. Không chạy test trên database đang dùng.

Hai lần thử phải dùng cùng URL, cookies và cấu hình. Thời gian xử lý và câu dịch
có thể thay đổi vì dịch vụ bên ngoài; so sánh thành công/thất bại, các mốc xử lý,
âm thanh, phụ đề và báo cáo runtime, không so hash MP4.

`run.bat` hiện mặc định dùng `%LOCALAPPDATA%/VideoDub` giống desktop. Nếu chạy
backend trực tiếp hoặc đặt `VIDEODUB_DATA_DIR`, cookies có thể nằm ở thư mục khác.
Không mở đồng thời hai backend trên cùng database khi thử: startup có cơ chế
đánh dấu tác vụ gián đoạn, có thể ảnh hưởng tác vụ của tiến trình kia.

## Kết quả kiểm tra Windows ngày 08/09/2026

Bản nguồn và EXE build tại máy đã vượt qua kiểm tra runtime và so sánh báo cáo.
34 kiểm thử liên quan đã qua. Chưa chạy xác minh thực tế trên macOS.

Với video Douyin `7682725748402620032`, cùng cookies và cấu hình ở trên,
cả nguồn và EXE tải thành công, trích âm thanh và nhận dạng được 207 đoạn.
Cả hai dừng ở bước dịch với 8/207 câu chưa dịch được; log có HTTP 504 từ
dịch vụ dịch dự phòng. Do đó chưa xác nhận được toàn bộ quy trình xuất video
cho mẫu này. Đây là kết quả kiểm tra tại thời điểm trên, không phải bảo đảm
dịch vụ bên ngoài luôn hoạt động.
