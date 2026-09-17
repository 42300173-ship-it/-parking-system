# BÁO CÁO TOÀN DIỆN ĐỒ ÁN TỐT NGHIỆP / ĐỒ ÁN CHUYÊN NGÀNH

## TÊN ĐỀ TÀI:
**NGHIÊN CỨU, THIẾT KẾ VÀ XÂY DỰNG HỆ THỐNG QUẢN LÝ BÃI ĐỖ XE THÔNG MINH ỨNG DỤNG IOT, RFID VÀ THỊ GIÁC MÁY TÍNH (COMPUTER VISION)**

---

## MỤC LỤC
1. [TỔNG QUAN VÀ TÍNH CẤP THIẾT CỦA ĐỀ TÀI](#1-tổng-quan-và-tính-cấp-thiết-của-đề-tài)
2. [KIẾN TRÚC TỔNG THỂ HỆ THỐNG](#2-kiến-trúc-tổng-thể-hệ-thống)
3. [THIẾT KẾ PHẦN CỨNG (HARDWARE DESIGN)](#3-thiết-kế-phần-cứng-hardware-design)
4. [GIAO THỨC TRUYỀN NHẬN DỮ LIỆU (DATA TRANSMISSION PROTOCOL)](#4-giao-thức-truyền-nhận-dữ-liệu-data-transmission-protocol)
5. [MODULE THỊ GIÁC MÁY TÍNH VÀ NHẬN DIỆN BIỂN SỐ AI](#5-module-thị-giác-máy-tính-và-nhận-diện-biển-số-ai)
6. [HỆ THỐNG CƠ SỞ DỮ LIỆU (DATABASE STORAGE)](#6-hệ-thống-cơ-sở-dữ-liệu-database-storage)
7. [PHẦN MỀM VÀ GIAO DIỆN WEB DASHBOARD (SOFTWARE & UI)](#7-phần-mềm-và-giao-diện-web-dashboard-software--ui)
8. [QUY TRÌNH HOẠT ĐỘNG THỰC TẾ (WORKFLOW CHI TIẾT)](#8-quy-trình-hoạt-động-thực-tế-workflow-chi-tiết)
9. [ĐÁNH GIÁ KẾT QUẢ, ƯU ĐIỂM VÀ HƯỚNG PHÁT TRIỂN](#9-đánh-giá-kết-quả-ưu-điểm-và-hướng-phát-triển)

---

## 1. TỔNG QUAN VÀ TÍNH CẤP THIẾT CỦA ĐỀ TÀI

### 1.1. Đặt vấn đề
Sự gia tăng nhanh chóng của các phương tiện giao thông tại các đô thị, trường học, tòa nhà và trung tâm thương mại đang đặt ra thách thức lớn trong công tác quản lý bãi đỗ xe. Các phương pháp truyền thống (ghi vé giấy, bảo vệ bấm thẻ thủ công) bộc lộ nhiều hạn chế:
- Tốc độ lưu thông chậm, dễ gây ùn tắc giờ cao điểm.
- Dễ mất mát, rách ướt vé xe; nguy cơ gian lận, tráo xe cao.
- Không nắm bắt được vị trí đỗ nào còn trống trong thời gian thực.
- Khó thống kê doanh thu và báo cáo minh bạch.

### 1.2. Mục tiêu đề tài
Xây dựng một hệ thống bãi đỗ xe thông minh tích hợp toàn diện:
1. **Tự động hóa hoàn toàn quy trình vào/ra**: Quét thẻ RFID là hệ thống tự động kích hoạt chụp ảnh và nhận diện biển số xe mà không cần bất kỳ thao tác bấm nút chụp hình thủ công nào.
2. **Giám sát vị trí đỗ thời gian thực**: Sử dụng cảm biến hồng ngoại (IR Sensor) để phát hiện và trực quan hóa trạng thái từng vị trí đỗ (C1, C2, C3) lên màn hình giám sát.
3. **Thị giác máy tính (AI Computer Vision)**: Ứng dụng mô hình Deep Learning (EasyOCR) kết hợp các giải thuật xử lý ảnh OpenCV để nhận diện biển số xe Việt Nam.
4. **Hệ thống cơ sở dữ liệu chuyên nghiệp (MySQL)**: Lưu trữ lịch sử xe vào, xe ra, thời gian gửi, hình ảnh chụp thực tế và tính toán chi phí gửi xe chính xác theo từng phút.
5. **Giao diện Web Dashboard hiện đại**: Thiết kế theo phong cách Glassmorphism trực quan, thân thiện, bảo mật cao.

---

## 2. KIẾN TRÚC TỔNG THỂ HỆ THỐNG

Hệ thống được thiết kế theo mô hình kiến trúc phân tầng kết hợp giữa **Phần cứng IoT (Edge Devices) -> Máy chủ Backend (Python Flask Server & AI Engine) -> Cơ sở dữ liệu (MySQL / SQLite) -> Giao diện người dùng (Web Dashboard HTML5/CSS3/JS)**.

- **Tầng Thiết bị (Device Layer)**: Vi điều khiển ESP32 giao tiếp với mô-đun đọc thẻ RFID RC522 (chuẩn SPI) và 3 cảm biến hồng ngoại dò vật cản đặt tại các ô đỗ C1, C2, C3. Webcam thu nhận luồng video liên tục.
- **Tầng Mạng (Network Layer)**: ESP32 phát tín hiệu qua Wi-Fi (chuẩn TCP/IP, giao thức HTTP RESTful API) gửi dữ liệu trực tiếp tới địa chỉ IP của máy chủ.
- **Tầng Xử lý Trung tâm (Server & AI Layer)**: Python Flask điều phối dữ liệu, chạy ngầm luồng đọc Camera, tự động trích xuất frame, ứng dụng OpenCV tiền xử lý và mạng nơ-ron EasyOCR nhận dạng biển số xe.
- **Tầng Dữ liệu (Data Layer)**: Máy chủ MySQL (thông qua XAMPP) quản lý cấu trúc bảng, liên kết dữ liệu quan hệ và chỉ mục tìm kiếm.
- **Tầng Trình diễn (Presentation Layer)**: Giao diện Web HTML5/CSS3 chuẩn Dashboard điều khiển trung tâm với công nghệ polling tự động cập nhật dữ liệu.

---

## 3. THIẾT KẾ PHẦN CỨNG (HARDWARE DESIGN)

### 3.1. Danh mục linh kiện phần cứng

| STT | Thiết Bị / Linh Kiện | Thông Số Kỹ Thuật | Vai Trò Trong Hệ Thống |
| :---: | :--- | :--- | :--- |
| 1 | **Vi điều khiển ESP32 (NodeMCU-32S)** | CPU Dual-core 240MHz, 520KB SRAM, tích hợp Wi-Fi 802.11 b/g/n và Bluetooth | Thu thập dữ liệu từ RFID và cảm biến IR, kết nối Wi-Fi gửi HTTP POST lên Server |
| 2 | **Đầu đọc thẻ RFID RC522** | Tần số 13.56 MHz, giao tiếp SPI, điện áp 3.3V | Đọc mã định danh duy nhất (UID) của thẻ gửi xe khi phương tiện tới cổng |
| 3 | **Cảm biến hồng ngoại IR (3 chiếc)** | Tầm quét 2 - 30cm, tín hiệu ngõ ra Digital (LOW khi có vật cản, HIGH khi trống) | Lắp đặt tại 3 vị trí đỗ C1, C2, C3 để giám sát thực tế có xe đỗ hay không |
| 4 | **Thẻ từ RFID Mifare 1K (Thẻ card/móc chìa khóa)** | Tần số 13.56MHz, chip S50, bộ nhớ 1KB | Đóng vai trò là vé xe phát cho người gửi |
| 5 | **Camera (Webcam USB / Camera tích hợp)** | Độ phân giải HD 720p / Full HD 1080p | Thu nhận hình ảnh video luồng cổng bãi xe và chụp ảnh biển số khi quét thẻ |

### 3.2. Sơ đồ đấu nối chân (Pinout Mapping)

#### A. Kết nối Đầu đọc RFID RC522 với ESP32 (Chuẩn SPI):
- **SDA (SS)**: GPIO 5
- **SCK**: GPIO 18
- **MOSI**: GPIO 23
- **MISO**: GPIO 19
- **IRQ**: Để trống
- **GND**: GND
- **RST**: GPIO 22
- **3.3V**: Nguồn 3.3V của ESP32 *(Lưu ý: Không cấp nguồn 5V vì sẽ làm cháy chip RC522)*

#### B. Kết nối Cảm biến hồng ngoại IR:
- **Cảm biến Vị trí C1**: Chân OUT nối vào **GPIO 13**
- **Cảm biến Vị trí C2**: Chân OUT nối vào **GPIO 12**
- **Cảm biến Vị trí C3**: Chân OUT nối vào **GPIO 14**
- **VCC**: Cấp nguồn 3.3V hoặc 5V
- **GND**: Nối chung mass GND với ESP32

---

## 4. GIAO THỨC TRUYỀN NHẬN DỮ LIỆU (DATA TRANSMISSION PROTOCOL)

Hệ thống sử dụng các giao thức mạng chuẩn công nghiệp, tối ưu hóa tốc độ và triệt tiêu độ trễ:

### 4.1. Giao thức HTTP RESTful API (ESP32 -> Server)

#### API 1: Quẹt thẻ RFID (Cổng Vào & Cổng Ra)
- **Endpoint**: `POST /api/rfid_scan`
- **Content-Type**: `application/json`
- **Dữ liệu gửi từ ESP32**:
  ```json
  {
      "rfid_uid": "E2801191A5"
  }
  ```
- **Xử lý tại Server**:
  - **Debounce 3 giây**: Lọc bỏ tín hiệu quét trùng lặp do người dùng giữ thẻ quá lâu.
  - **Phân loại Luồng Vào / Luồng Ra**:
    - Nếu `rfid_uid` **đã tồn tại** trong vị trí đỗ: Kích hoạt quy trình **XE RA** -> Tự động chụp ảnh -> Tạo bản ghi `pending_exit` -> Tính phí tạm tính.
    - Nếu `rfid_uid` **chưa tồn tại**: Kích hoạt quy trình **XE VÀO** -> Tự động cắt 1 frame từ Camera -> Chạy EasyOCR -> Tìm vị trí trống C1 -> C2 -> C3 -> Gán vào CSDL.
- **Phản hồi trả về (Response 200 OK)**:
  ```json
  {
      "status": "entry_success",
      "action": "entry",
      "rfid_uid": "E2801191A5",
      "slot": "C1",
      "plate": "51A-123.45",
      "image_url": "/captures/entry_20260914_171430_404.jpg"
  }
  ```

#### API 2: Cập nhật cảm biến hồng ngoại IR (Vị trí đỗ)
- **Endpoint**: `POST /api/update_slot`
- **Dữ liệu gửi**: `{"slot": "C1", "status": "F"}` *(F = Full/Có xe, E = Empty/Trống)*
- **Ý nghĩa kiến trúc**: Tách rời hoàn toàn giữa màu cảm biến IR và dữ liệu thẻ RFID. Nhờ đó, cảm biến IR chỉ làm nhiệm vụ hiển thị đèn xanh/đỏ thực tế, không gây xung đột hay làm sai lệch việc tính toán chi phí đỗ xe.

### 4.2. Giao thức Truyền Video Trực Tiếp (MJPEG Streaming)
- **Endpoint**: `GET /video_feed`
- **MIME-Type**: `multipart/x-mixed-replace; boundary=frame`
- **Nguyên lý hoạt động**:
  1. Luồng chạy nền (`CameraStream`) liên tục đọc khung hình từ thiết bị phần cứng thông qua backend OpenCV `cv2.CAP_DSHOW` để đạt tốc độ khởi động nhanh nhất.
  2. Mỗi khung hình được nén sang định dạng JPEG ở chất lượng tối ưu (75%).
  3. Server truyền luồng nhị phân liên tục tới thẻ `<img>` của HTML5 trên trình duyệt. Trình duyệt liên tục thay thế ảnh cũ bằng ảnh mới tạo thành video mượt mà 30 FPS mà không cần bất kỳ plugin hay phần mềm trung gian nào.

---

## 5. MODULE THỊ GIÁC MÁY TÍNH VÀ NHẬN DIỆN BIỂN SỐ AI

Điểm đột phá quan trọng nhất của đồ án là **xóa bỏ nút bấm chụp ảnh thủ công**, chuyển thành **cơ chế chụp và nhận diện tự động tức thì**:

### 5.1. Thuật toán tiền xử lý ảnh (OpenCV Pipeline)
1. **Chuyển đổi không gian màu (Grayscale)**: `cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)` loại bỏ kênh màu, giảm dung lượng dữ liệu tính toán.
2. **Khử nhiễu (Gaussian Blur)**: Sử dụng ma trận lọc `(5, 5)` làm mịn ảnh, loại bỏ các chi tiết nhiễu hạt nhỏ trên bề mặt vỏ xe.
3. **Phát hiện cạnh biên (Canny Edge Detection)**: Sử dụng ngưỡng kép `(50, 200)` để làm nổi bật các cạnh viền hình chữ nhật của biển số.
4. **Tìm kiếm đường viền (Contour Approximation)**: 
   - Dùng `cv2.findContours` và lọc đa giác 4 đỉnh (`cv2.approxPolyDP`).
   - Kiểm tra tỷ lệ khung hình (Aspect Ratio `w / h` từ 0.8 đến 5.5) và kích thước tối thiểu để xác định chính xác vị trí biển số.

### 5.2. Giải pháp xử lý biển số xe máy 2 dòng (Biển vuông)
- Biển số xe máy Việt Nam thường có 2 dòng (Dòng trên: Tỉnh thành + Sê-ri, Dòng dưới: 4 hoặc 5 số). Nếu đưa trực tiếp vào mô hình OCR thì EasyOCR thường đọc nhầm thứ tự dòng.
- **Giải pháp giải thuật**: Hệ thống tự động cắt nửa trên (`top_half`) và nửa dưới (`bottom_half`), sau đó ghép nối ngang (`np.hstack`) tạo thành một dòng chữ nhật nằm ngang trước khi đưa vào EasyOCR. Độ chính xác nhận diện tăng hơn 45% so với đọc trực tiếp.

### 5.3. Hậu xử lý bằng Biểu thức chính quy (Regex Post-processing)
EasyOCR đôi khi nhầm lẫn các ký tự quang học có hình dạng tương đồng dưới điều kiện ánh sáng yếu. Hàm `clean_plate_text` thực hiện chuẩn hóa:
- Đổi số thành chữ ở vị trí chữ cái sê-ri: `5 -> S`, `8 -> B`, `0 -> D`, `6 -> G`, `2 -> Z`.
- Đổi chữ thành số ở vị trí mã tỉnh thành và số thứ tự: `B -> 5`, `S -> 5`, `O/D/Q -> 0`.
- Kiểm tra khớp định dạng chuẩn Việt Nam:
  - Xe máy: `\d{2}[A-Z]\d-\d{4,5}` (Ví dụ: `59A1-123.45` hoặc `18A1-2345`).
  - Ô tô: `\d{2}[A-Z]-\d{3}\.\d{2}` (Ví dụ: `51A-123.45`).

---

## 6. HỆ THỐNG CƠ SỞ DỮ LIỆU (DATABASE STORAGE)

Hệ thống sử dụng cơ sở dữ liệu quan hệ chuẩn **MySQL** (chạy trên máy chủ Apache/MySQL của XAMPP) với tính năng tự động chuyển mạch sang SQLite dự phòng nếu MySQL gặp sự cố.

### 6.1. Chi tiết lược đồ Cơ sở dữ liệu (Database Schema)

#### 1. Bảng `logs` (Quản lý lượt xe VÀO)
| Tên Cột | Kiểu Dữ Liệu | Khóa | Diễn Giải |
| :--- | :--- | :---: | :--- |
| `id` | `INT` | **PK (AI)** | Mã lượt gửi (Tự động tăng) |
| `timestamp` | `VARCHAR(50)` | | Thời gian xe vào (`dd/mm/yyyy HH:MM:SS`) |
| `slot_name` | `VARCHAR(20)` | | Vị trí đỗ được phân bổ (`C1`, `C2`, `C3`) |
| `plate_number` | `VARCHAR(50)` | | Biển số xe nhận diện được từ AI |
| `rfid_uid` | `VARCHAR(50)` | | Mã thẻ RFID của xe |
| `image_path` | `VARCHAR(255)`| | Đường dẫn file ảnh chụp thực tế lúc xe vào |
| `created_at` | `TIMESTAMP` | | Thời điểm tạo bản ghi hệ thống |

#### 2. Bảng `exit_logs` (Quản lý lượt xe RA và Thu phí)
| Tên Cột | Kiểu Dữ Liệu | Khóa | Diễn Giải |
| :--- | :--- | :---: | :--- |
| `id` | `INT` | **PK (AI)** | Mã lượt ra |
| `slot_name` | `VARCHAR(20)` | | Vị trí đỗ của xe |
| `plate_number` | `VARCHAR(50)` | | Biển số xe đối chiếu |
| `rfid_uid` | `VARCHAR(50)` | | Mã thẻ RFID |
| `time_in` | `VARCHAR(50)` | | Thời gian xe vào bãi |
| `time_out` | `VARCHAR(50)` | | Thời gian xe ra bãi |
| `fee` | `INT` | | Tiền gửi xe thực tế đã thu (VND) |
| `image_path` | `VARCHAR(255)`| | Ảnh chụp xe tại thời điểm ra cổng |

#### 3. Bảng `slot_status` (Trạng thái hiện tại của từng ô đỗ)
| Tên Cột | Kiểu Dữ Liệu | Khóa | Diễn Giải |
| :--- | :--- | :---: | :--- |
| `slot_name` | `VARCHAR(10)` | **PK** | Tên vị trí đỗ (`C1`, `C2`, `C3`) |
| `status` | `VARCHAR(5)` | | Trạng thái cảm biến IR (`E` = Trống, `F` = Có xe) |
| `time_in` | `VARCHAR(50)` | | Giờ vào của xe đang đỗ |
| `time_out` | `VARCHAR(50)` | | Giờ ra của lượt xe trước đó |
| `last_fee` | `INT` | | Phí của lượt gửi gần nhất |
| `current_plate`| `VARCHAR(50)` | | Biển số xe hiện tại đang giữ vị trí |
| `current_rfid` | `VARCHAR(50)` | | Mã thẻ RFID hiện tại đang giữ vị trí |
| `image_path` | `VARCHAR(255)`| | Ảnh chụp xe đang đỗ |

#### 4. Bảng `pending_exit` (Hàng đợi xác nhận xe ra)
- Lưu trữ tạm thời các xe đã quẹt thẻ lần 2 tại cổng ra.
- Cho phép nhân viên bảo vệ kiểm tra đối chiếu biển số trên màn hình Web trước khi bấm *"Xác nhận cho xe ra"*.

#### 5. Bảng `revenue` (Tổng doanh thu)
- Lưu trữ con số tổng tiền lũy kế thu được của toàn bộ bãi xe.

---

## 7. PHẦN MỀM VÀ GIAO DIỆN WEB DASHBOARD (SOFTWARE & UI)

### 7.1. Kiến trúc mã nguồn phần mềm

```
doanCN.py/
│── app.py                 # File thực thi chính: Khởi động Flask Server, điều phối REST API
│── camera.py              # Xử lý luồng Camera nền, tạo luồng video MJPEG, chụp snapshot
│── ocr_engine.py          # AI Engine: Cắt đường viền biển số, EasyOCR và Regex làm sạch
│── database.py            # Lớp trừu tượng CSDL: Tự động phát hiện và chuyển đổi MySQL/SQLite
│── config.py              # File cấu hình tập trung (IP, Port, Cước phí, Mật khẩu, DB)
│── .env                   # Lưu cấu hình môi trường bảo mật
│── schema.sql             # Script SQL tạo Database và bảng cho MySQL / phpMyAdmin
│── start_system.bat       # Phím tắt 1-click tự động khởi động toàn bộ hệ thống
│── captures/              # Thư mục chứa toàn bộ ảnh chụp xe vào và ra
│── templates/
│   └── index.html         # Giao diện Web Dashboard HTML5 cấu trúc ngữ nghĩa
└── static/
    ├── css/style.css      # Thiết kế giao diện Glassmorphism Dark Theme, hiệu ứng LED Neon
    ├── js/app.js          # Logic phía Client: Cập nhật AJAX, đồng hồ bấm giờ, thông báo Toast
    └── img/no_signal.svg  # Ảnh vector fallback khi camera mất kết nối
```

### 7.2. Đặc điểm nổi bật của giao diện Web:
1. **Thiết kế Glassmorphism Dark Mode**: Nền tối bảo vệ mắt, hiệu ứng kính mờ và viền phát sáng công nghệ cao, phù hợp với các trung tâm điều hành giám sát.
2. **Đồng hồ đỗ xe thời gian thực (Live Stopwatch)**: Mỗi ô đỗ có xe sẽ hiển thị thời gian đỗ xe nhảy theo từng phút, từng giây; tiền gửi tạm tính tăng theo thời gian thực.
3. **Thanh trạng thái trực quan**: Thống kê số lượng chỗ đỗ còn lại (`X / 3`), tổng doanh thu tích lũy, đồng hồ hệ thống.
4. **Bảo mật và Phân quyền**: Đăng nhập bằng tài khoản và mật khẩu, hỗ trợ cơ chế khôi phục bằng mã PIN quản trị viên khẩn cấp.

---

## 8. QUY TRÌNH HOẠT ĐỘNG THỰC TẾ (WORKFLOW CHI TIẾT)

### 8.1. Kịch bản 1: Xe vào bãi (Check-in)
1. Xe dừng trước cổng, người gửi đưa thẻ RFID lại gần đầu đọc RC522.
2. ESP32 đọc mã UID và gửi lệnh `POST /api/rfid_scan` kèm mã UID lên Server qua Wi-Fi.
3. Server nhận tín hiệu, xác định đây là thẻ mới (chưa có trong bãi):
   - **Ngay lập tức chụp 1 khung hình từ Camera** và lưu vào thư mục `captures/entry_...jpg`.
   - Đưa khung hình vào bộ lọc OpenCV để xác định tọa độ biển số và cắt vùng quan tâm (ROI).
   - Đưa vùng ảnh cắt vào mạng EasyOCR để trích xuất ký tự biển số.
   - Chuẩn hóa ký tự qua hàm Regex.
   - Tìm vị trí đỗ còn trống đầu tiên theo thứ tự ưu tiên `C1 -> C2 -> C3`.
   - Ghi dữ liệu vào bảng `logs` và cập nhật vị trí trong `slot_status`.
4. Trên giao diện Web:
   - Thẻ vị trí đỗ chuyển sang màu đỏ (hoặc xanh theo cảm biến IR), hiển thị biển số xe, giờ vào và bắt đầu tính thời gian đỗ.
   - Hộp thông tin *"Ảnh vừa quét"* hiển thị ảnh chụp xe cùng biển số vừa nhận diện.

### 8.2. Kịch bản 2: Xe đỗ trong bãi (Parking)
- Cảm biến hồng ngoại IR tại vị trí C1/C2/C3 liên tục gửi tín hiệu `POST /api/update_slot` lên Server.
- Khi người lái xe đưa xe vào vị trí, cảm biến IR phát hiện vật cản (trạng thái `F`) -> Thẻ vị trí trên Web chuyển sang màu đỏ cảnh báo.
- Tiền gửi xe được tự động tính lũy kế:
  - $\text{Số phút gửi} = \lceil (\text{Thời gian hiện tại} - \text{Thời gian vào}) / 60 \rceil$
  - $\text{Cước phí} = \max(1.000, \text{Số phút} \times 1.000 \text{ VND})$

### 8.3. Kịch bản 3: Xe ra khỏi bãi (Check-out & Tính phí)
1. Người gửi xe quẹt thẻ RFID lần 2 tại cổng ra.
2. ESP32 gửi mã UID lên Server. Server kiểm tra thấy thẻ này đang đỗ tại vị trí (ví dụ `C1`):
   - Server tự động chụp một bức ảnh xe lúc ra.
   - Tạo yêu cầu chờ trong bảng `pending_exit` và tính toán tổng số tiền gửi xe cần thu.
3. Trên giao diện Web Dashboard:
   - Một thẻ thông báo màu vàng nhấp nháy **"Yêu Cầu Xe Ra Đang Chờ Xác Nhận"** xuất hiện ngay lập tức.
   - Hiển thị biển số xe lúc vào, giờ vào, tổng thời gian gửi và tổng tiền cước phí cần thu.
4. Nhân viên bảo vệ đối chiếu biển số thực tế của xe trước cổng với thông tin trên màn hình:
   - Nếu đúng: Bảo vệ bấm nút **[ Xác Nhận Xe Ra ]** -> Hệ thống thu tiền, ghi nhận vào bảng `exit_logs`, cộng tiền vào tổng doanh thu bãi xe và giải phóng vị trí `C1` về trạng thái Trống.
   - Nếu sai hoặc nhầm thẻ: Bấm **[ Hủy ]** để kiểm tra lại.

---

## 9. ĐÁNH GIÁ KẾT QUẢ, ƯU ĐIỂM VÀ HƯỚNG PHÁT TRIỂN

### 9.1. Các kết quả đã đạt được
1. **Khắc phục triệt để nhược điểm của phiên bản cũ**:
   - Loại bỏ hoàn toàn sự xung đột giữa hiển thị Camera và nhận dữ liệu từ ESP32 trên Streamlit.
   - Bỏ hoàn toàn thao tác thủ công người dùng phải bấm nút chụp ảnh trước khi quẹt thẻ.
2. **Thời gian xử lý nhanh chóng**:
   - Tốc độ chụp ảnh và nhận diện biển số trung bình đạt từ **0.3s - 0.8s**, đảm bảo xe lưu thông trơn tru không bị ùn ứ.
3. **Cơ sở dữ liệu tiêu chuẩn công nghiệp (MySQL)**:
   - Dữ liệu được lưu trữ có cấu trúc rõ ràng, hỗ trợ truy vấn nhanh, dễ dàng xuất báo cáo và tích hợp với các hệ thống phần mềm quản lý doanh nghiệp.
4. **Vận hành tiện lợi**:
   - Khởi động 1-click thông qua file `start_system.bat`.
   - Sẵn sàng demo di động thông qua điểm phát sóng Wi-Fi 4G/5G cá nhân mà không phụ thuộc vào hạ tầng mạng của trường học.

### 9.2. Hướng phát triển trong tương lai
- **Điều khiển rào chắn Barrier tự động**: Bổ sung động cơ Servo SG90 hoặc Relay để tự động nâng thanh chắn khi nhận diện hợp lệ.
- **Thanh toán không tiền mặt**: Tích hợp tạo mã QR thanh toán động (VietQR / MoMo / ZaloPay) hiển thị trực tiếp lên màn hình Web khi xe ra.
- **Mở rộng nhận diện khuôn mặt**: Bổ sung Camera nhận diện khuôn mặt người điều khiển xe để tăng cường mức độ bảo mật chống mất trộm phương tiện.
