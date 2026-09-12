# VideoDub: license cho một thiết bị

## Phạm vi đã thống nhất

Mỗi license chỉ kích hoạt trên một thiết bị. Chủ sản phẩm tạo mã, đặt hạn dùng,
khóa mã và duyệt đổi máy. App xác thực định kỳ qua máy chủ và được ngoại tuyến
tối đa 72 giờ sau lần xác thực thành công, không vượt quá hạn license.

## Lựa chọn kiến trúc

- Chọn máy chủ license riêng bằng FastAPI, cùng hệ sinh thái Python hiện tại.
  Có thêm chi phí vận hành nhưng kiểm soát được kích hoạt, thu hồi và đổi máy.
- Mã ký ngoại tuyến đơn thuần giảm vận hành nhưng không thu hồi kịp thời.
- Dịch vụ license thuê ngoài giảm công xây dựng nhưng thêm phí và phụ thuộc nhà cung cấp.

Máy chủ license và database của nó không được đóng gói trong bộ cài khách hàng.
Bản đầu dùng SQLite trên một máy chủ, giao dịch nguyên tử khi nhận thiết bị;
không chạy nhiều bản sao máy chủ với database rời nhau. Cung cấp hướng dẫn triển
khai với HTTPS, volume dữ liệu bền vững và sao lưu. Chưa chọn nhà cung cấp hosting.

## Kích hoạt và quyền sử dụng

App hiển thị màn hình nhập mã, tên thiết bị, trạng thái và hạn license. Thiết bị
được nhận diện từ định danh hệ điều hành Windows/macOS, băm trước khi gửi;
không dùng địa chỉ MAC vì dễ đổi. Không thu thập cookies, nội dung video hay API key.
Nếu không đọc được định danh hợp lệ, báo lỗi rõ ràng thay vì dùng ID chung.
Cài lại hệ điều hành có thể cần chủ sản phẩm duyệt đổi thiết bị.

Máy chủ lưu hash mã license ngẫu nhiên đủ mạnh, không ghi mã đầy đủ vào log.
Kích hoạt thiết bị đầu tiên là một giao dịch; hai thiết bị tranh cùng mã chỉ
một thiết bị thành công. Kích hoạt lại trên thiết bị đã liên kết là idempotent.

Máy chủ cấp chứng nhận có chữ ký bất đối xứng, chứa mã license nội bộ, hash thiết
bị, thời điểm cấp, hạn ngoại tuyến và phiên bản liên kết thiết bị. App chỉ có
khóa công khai để xác minh; khóa ký riêng và thông tin quản trị chỉ ở máy chủ.
Chứng nhận của máy khác, bị sửa, hết hạn hoặc sai chữ ký đều bị từ chối.

App xác thực lúc mở, định kỳ khi đang mở và trước tác vụ xử lý mới nếu dữ liệu
xác thực quá cũ. Chỉ lỗi mạng/máy chủ tạm thời mới dùng chứng nhận còn hạn.
Phản hồi khóa mã/đổi máy/hết hạn sẽ vô hiệu hóa quyền đã lưu ngay. Máy cũ đang
offline có thể còn dùng tối đa thời gian ngoại tuyến còn lại; không hứa thu hồi
tức thì khi mất mạng. Phát hiện đồng hồ quay lùi thì yêu cầu xác thực online;
đây không phải bảo vệ tuyệt đối trước người sửa hệ điều hành hoặc mã chương trình.

## Tích hợp VideoDub

Kiểm tra quyền trong backend trước tải video, tạo giọng và bắt đầu xử lý; không
chỉ khóa nút ở giao diện. Cho phép xem trạng thái, kích hoạt, xem lịch sử và lấy
kết quả cũ khi hết hạn. Tác vụ đã chấp nhận được hoàn tất để không mất công xử lý.
Trạng thái lỗi hiển thị cách liên hệ chủ sản phẩm để đổi máy hoặc gia hạn.

Bản thương mại yêu cầu URL máy chủ và khóa công khai lúc build; thiếu cấu hình
thì build thất bại. Không có biến môi trường cho khách tắt license trong EXE.
Chế độ phát triển nội bộ được tách rõ, không vô tình khóa run.bat của chủ sản phẩm.
Workflow kiểm tra đóng gói chạy bài test nội bộ mà không cung cấp đường chạy
pipeline bỏ qua license trong bản thương mại phát hành cho khách.

## Quản trị

Giao diện quản trị trên máy chủ có đăng nhập, cookie phiên an toàn, kiểm tra CSRF
với thao tác thay đổi và giới hạn thử đăng nhập/kích hoạt. Không đưa thông tin
đăng nhập quản trị vào frontend của app khách. Có chức năng tạo mã, đặt hạn,
khóa/mở khóa, xem thiết bị, thu hồi liên kết để đổi máy và nhật ký thao tác.
Không tự động thanh toán hay tự động chuyển máy trong phiên bản đầu.

## Kiểm chứng và bàn giao

Kiểm thử kích hoạt lần đầu, kích hoạt lại, tranh chấp hai thiết bị, sai thiết bị,
thu hồi, hết hạn, ngoại tuyến, giả mạo chứng nhận, quay lùi đồng hồ, quyền quản trị
và các API xử lý bị chặn. Kiểm tra run.bat nội bộ vẫn hoạt động, build thiếu cấu
hình phải thất bại, và bản thương mại không có CLI xử lý bỏ qua license.

Chạy thử server và app với license mẫu trong dữ liệu riêng trước khi triển khai.
Chỉ xác nhận hoạt động ngoài internet sau khi có hosting, HTTPS và kiểm tra thực tế.
Không thay đổi tính công khai repository hoặc phát hành bộ cài khi chưa có yêu cầu.
Mã nguồn công khai hoặc xử lý hoàn toàn trên máy khách có thể bị sửa để bỏ license;
giải pháp hạn chế chia sẻ thông thường, không bảo đảm ngăn bán lại/bẻ khóa tuyệt đối.
