import os
import time
from datetime import datetime
from flask import Flask, jsonify, render_template, request, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

# Load biến môi trường từ .env
load_dotenv()

import config
from database import db
from camera import camera
from ocr_engine import ocr

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

_last_rfid_time = {}
latest_scan_event = {}


@app.route("/")
def index():
    """Trang chủ Dashboard hệ thống bãi đỗ xe."""
    return render_template("index.html")


@app.route("/captures/<path:filename>")
def serve_capture(filename):
    """Phục vụ ảnh chụp xe vào / xe ra từ thư mục captures/."""
    return send_from_directory(config.CAPTURES_DIR, filename)


@app.route("/video_feed")
def video_feed():
    """Stream MJPEG thời gian thực từ Camera lên trình duyệt web."""
    return Response(
        camera.generate_mjpeg_stream(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


def parse_request_payload():
    return request.get_json(silent=True) or request.form.to_dict() or {}


# =====================================================
# API CHO THIẾT BỊ PHẦN CỨNG (ESP32 / ARDUINO)
# =====================================================

@app.route("/api/update_slot", methods=["POST", "GET"])
def update_slot():
    """
    CẢM BIẾN HỒNG NGOẠI (IR): ESP32 gửi slot=C1/C2/C3 và status=F (có xe) / E (trống).
    Chỉ đổi màu trạng thái trên Web, không ảnh hưởng logic thẻ RFID.
    """
    if request.method == "GET":
        return jsonify({"status": "ok", "message": "API update_slot dang hoat dong"}), 200

    data = parse_request_payload()
    slot = data.get("slot")
    status = data.get("status")
    if slot and status:
        db.ir_update_slot(slot, status)
        return jsonify({"status": "ir_ok", "slot": slot, "ir": status}), 200
    return jsonify({"status": "error", "message": "Thieu tham so slot hoac status"}), 400


@app.route("/api/rfid_scan", methods=["POST"])
def rfid_scan():
    """
    QUÉT THẺ RFID TỪ ESP32:
    - Thẻ LẠ (Xe Vào): Chụp ảnh, đọc biển số và đưa vào danh sách chờ xác nhận.
    - Thẻ TRÙNG (Xe Ra): Quét lần 2 -> Tự động chụp ảnh lúc ra -> Tạo Pending Exit chờ bảo vệ xác nhận.
    """
    global latest_scan_event
    data = parse_request_payload()
    rfid_uid = data.get("rfid_uid") or data.get("uid") or "UNKNOWN"

    now_ts = time.time()
    last_ts = _last_rfid_time.get(rfid_uid, 0)
    if now_ts - last_ts < config.RFID_DEBOUNCE_SEC:
        print(f"[RFID DEBOUNCE] Bo qua scan lap trong {config.RFID_DEBOUNCE_SEC}s: {rfid_uid}")
        return jsonify({"status": "duplicate_ignored", "rfid_uid": rfid_uid}), 200
    _last_rfid_time[rfid_uid] = now_ts

    # 1. KIỂM TRA XE RA: Thẻ này có đang đỗ trong bãi không?
    existing_slot = db.find_slot_by_rfid(rfid_uid)
    if existing_slot is not None:
        # Chụp ảnh xe lúc ra
        rel_img_path, _ = camera.capture_snapshot(prefix="exit")
        created = db.request_exit_pending(existing_slot, image_path=rel_img_path)
        print(f"[RFID XE RA] Thẻ {rfid_uid} tại {existing_slot} -> Đưa vào danh sách chờ xác nhận!")

        latest_scan_event = {
            "action": "XE RA (CHỜ DUYỆT)",
            "rfid": rfid_uid,
            "slot": existing_slot,
            "plate": "ĐANG CHỜ DUYỆT",
            "image_url": f"/{rel_img_path}" if rel_img_path else "",
            "timestamp": time.time()
        }

        return jsonify({
            "status": "exit_pending",
            "action": "exit_pending",
            "rfid_uid": rfid_uid,
            "slot": existing_slot,
            "message": "Da tao yeu cau cho bao ve xac nhan xe ra"
        }), 200

    # 2. XE VÀO: Tìm vị trí đỗ trống đầu tiên (C1 -> C2 -> C3)
    slot = db.find_first_empty_slot()
    if slot is None:
        print("[RFID XE VAO] BÃI ĐÃ ĐẦY - Từ chối nhận xe.")
        return jsonify({"status": "parking_full", "message": "Bai da day, khong con cho trong"}), 200

    # TỰ ĐỘNG CHỤP KHUNG HÌNH TỪ CAMERA
    rel_img_path, frame_bgr = camera.capture_snapshot(prefix="entry")

    # TỰ ĐỘNG NHẬN DIỆN BIỂN SỐ BẰNG EASYOCR
    detected_plate, is_valid = ocr.recognize_plate(frame_bgr)
    print(f"[RFID XE VAO] Thẻ mới {rfid_uid} -> Tự động chụp & nhận diện biển số: {detected_plate} (Vị trí: {slot})")

    if not is_valid:
        latest_scan_event = {
            "action": "XE VÀO (QUÉT LẠI)",
            "rfid": rfid_uid,
            "slot": slot,
            "plate": "KHÔNG XÁC ĐỊNH",
            "image_url": f"/{rel_img_path}" if rel_img_path else "",
            "timestamp": time.time()
        }
        return jsonify({
            "status": "entry_rescan_required",
            "action": "entry_rescan_required",
            "rfid_uid": rfid_uid,
            "slot": slot,
            "plate": "KHÔNG XÁC ĐỊNH",
            "image_url": f"/{rel_img_path}" if rel_img_path else "",
            "message": "Khong nhan dien duoc bien so, vui long dua xe vao dung vi tri va quet lai"
        }), 200

    # Chỉ tạo yêu cầu chờ; chỉ khi bảo vệ xác nhận mới ghi vào logs.
    db.request_entry_pending(
        slot, plate_number=detected_plate, rfid_uid=rfid_uid, image_path=rel_img_path
    )

    latest_scan_event = {
        "action": "XE VÀO (CHỜ DUYỆT)",
        "rfid": rfid_uid,
        "slot": slot,
        "plate": detected_plate,
        "image_url": f"/{rel_img_path}" if rel_img_path else "",
        "timestamp": time.time()
    }

    return jsonify({
        "status": "entry_pending",
        "action": "entry_pending",
        "rfid_uid": rfid_uid,
        "slot": slot,
        "plate": detected_plate,
        "image_url": f"/{rel_img_path}" if rel_img_path else ""
    }), 200


# =====================================================
# API CHO GIAO DIỆN WEB (DASHBOARD MANAGEMENT)
# =====================================================

@app.route("/api/status", methods=["GET"])
def get_system_status():
    """Lấy toàn bộ trạng thái hệ thống: doanh thu, 3 vị trí đỗ, danh sách chờ xe ra."""
    selected_date = request.args.get("date") or datetime.now().strftime("%d/%m/%Y")
    data = db.get_slots_status()
    data["total_revenue"] = db.get_daily_revenue(selected_date)
    data["selected_date"] = selected_date
    pending_exits = db.get_pending_exits()
    pending_entries = db.get_pending_entries()
    data["pending_exits"] = pending_exits
    data["pending_entries"] = pending_entries
    data["latest_scan"] = latest_scan_event
    data["db_type"] = db.db_type.upper()
    return jsonify(data), 200


@app.route("/api/confirm_exit", methods=["POST"])
def confirm_exit():
    """Bảo vệ bấm nút 'Xác nhận xe ra' trên Web."""
    data = parse_request_payload()
    slot = data.get("slot")
    if not slot:
        return jsonify({"status": "error", "message": "Thieu vi tri slot"}), 400

    res = db.confirm_exit_pending(slot)
    if res:
        global latest_scan_event
        latest_scan_event = {}
        return jsonify({"status": "ok", "message": "Da xac nhan cho xe ra", "fee": res["fee"]}), 200
    return jsonify({"status": "error", "message": "Khong tim thay yeu cau cho slot nay"}), 404


@app.route("/api/confirm_entry", methods=["POST"])
def confirm_entry():
    """Bảo vệ xác nhận xe vào sau khi OCR đọc đúng biển số."""
    data = parse_request_payload()
    slot = data.get("slot")
    if not slot:
        return jsonify({"status": "error", "message": "Thieu vi tri slot"}), 400
    res = db.confirm_entry_pending(slot)
    if res:
        global latest_scan_event
        latest_scan_event = {
            "action": "XE VÀO",
            "rfid": res["rfid"],
            "slot": res["slot"],
            "plate": res["plate"],
            "timestamp": time.time()
        }
        return jsonify({"status": "ok", "message": "Da xac nhan cho xe vao"}), 200
    return jsonify({"status": "error", "message": "Khong tim thay yeu cau cho slot nay"}), 404


@app.route("/api/cancel_exit", methods=["POST"])
def cancel_exit():
    """Bảo vệ hủy yêu cầu xe ra."""
    data = parse_request_payload()
    slot = data.get("slot")
    if slot:
        db.cancel_exit_pending(slot)
        global latest_scan_event
        latest_scan_event = {}
        return jsonify({"status": "ok", "message": "Da huy yeu cau xe ra"}), 200
    return jsonify({"status": "error", "message": "Thieu vi tri slot"}), 400


@app.route("/api/cancel_entry", methods=["POST"])
def cancel_entry():
    """Hủy yêu cầu xe vào đang chờ xác nhận."""
    data = parse_request_payload()
    slot = data.get("slot")
    if slot:
        db.cancel_entry_pending(slot)
        return jsonify({"status": "ok", "message": "Da huy yeu cau xe vao"}), 200
    return jsonify({"status": "error", "message": "Thieu vi tri slot"}), 400


@app.route("/api/manual_capture", methods=["POST"])
def manual_capture():
    """Bấm nút chụp thử nghiệm trên giao diện Web mà không cần quẹt thẻ."""
    global latest_scan_event
    rel_img_path, frame_bgr = camera.capture_snapshot(prefix="manual")
    detected_plate, is_valid = ocr.recognize_plate(frame_bgr)

    latest_scan_event = {
        "action": "CHỤP THỬ NGHIỆM",
        "rfid": "",
        "slot": "",
        "plate": detected_plate,
        "image_url": f"/{rel_img_path}" if rel_img_path else "",
        "timestamp": time.time()
    }

    return jsonify({
        "status": "ok",
        "plate": detected_plate,
        "image_url": f"/{rel_img_path}" if rel_img_path else ""
    }), 200


@app.route("/api/manual_assign", methods=["POST"])
def manual_assign():
    """Nhập tay biển số xe nếu OCR đọc sai."""
    global latest_scan_event
    data = parse_request_payload()
    plate = (data.get("plate") or "").strip().upper()
    if not plate:
        return jsonify({"status": "error", "message": "Chưa nhập biển số"}), 400

    occupied_slot = db.find_slot_by_plate(plate)
    if occupied_slot is not None:
        rel_img_path, _ = camera.capture_snapshot(prefix="manual_exit")
        db.request_exit_pending(occupied_slot, image_path=rel_img_path)
        latest_scan_event = {
            "action": "XE RA (GÁN TAY)",
            "rfid": "",
            "slot": occupied_slot,
            "plate": plate,
            "image_url": f"/{rel_img_path}" if rel_img_path else "",
            "timestamp": time.time()
        }
        return jsonify({
            "status": "exit_pending",
            "slot": occupied_slot,
            "plate": plate,
            "message": "Da tao yeu cau cho xe ra xac nhan"
        }), 200

    slot = db.find_first_empty_slot()
    if slot is None:
        return jsonify({"status": "error", "message": "Bãi đã đầy"}), 400

    simulated_uid = f"TAY_{datetime.now().strftime('%H%M%S')}"
    db.request_entry_pending(slot, plate_number=plate, rfid_uid=simulated_uid)

    latest_scan_event = {
        "action": "XE VÀO (GÁN TAY - CHỜ DUYỆT)",
        "rfid": simulated_uid,
        "slot": slot,
        "plate": plate,
        "timestamp": time.time()
    }

    return jsonify({"status": "entry_pending", "slot": slot, "plate": plate}), 200


@app.route("/api/reset_ir", methods=["POST"])
def reset_ir():
    """Reset trạng thái 3 ô và xóa thông tin xe hiện tại, không xóa lịch sử."""
    db.reset_slots()
    global latest_scan_event
    latest_scan_event = {}
    return jsonify({"status": "ok", "message": "Da reset trang thai cac o"}), 200


@app.route("/api/logs/in", methods=["GET"])
def get_logs_in():
    """Lấy danh sách lịch sử xe vào."""
    date_filter = request.args.get("date") or datetime.now().strftime("%d/%m/%Y")
    return jsonify({"status": "ok", "date": date_filter, "logs": db.get_all_logs(date_filter)}), 200


@app.route("/api/logs/out", methods=["GET"])
def get_logs_out():
    """Lấy danh sách lịch sử xe ra."""
    date_filter = request.args.get("date") or datetime.now().strftime("%d/%m/%Y")
    return jsonify({"status": "ok", "date": date_filter, "logs": db.get_all_exit_logs(date_filter)}), 200


@app.route("/api/logs/in/<int:log_id>", methods=["DELETE"])
def delete_log_in(log_id):
    db.delete_log_by_id(log_id)
    return jsonify({"status": "ok"}), 200


@app.route("/api/logs/out/<int:log_id>", methods=["DELETE"])
def delete_log_out(log_id):
    db.delete_exit_log_by_id(log_id)
    return jsonify({"status": "ok"}), 200


@app.route("/api/database/clear", methods=["POST"])
def clear_db():
    """Xóa sạch CSDL để kiểm thử lại từ đầu."""
    db.clear_all_logs()
    return jsonify({"status": "ok", "message": "Da xoa toan bo CSDL"}), 200


@app.route("/api/login", methods=["POST"])
def login():
    """Xác thực đăng nhập bảo vệ."""
    data = parse_request_payload()
    user = data.get("username", "")
    pwd = data.get("password", "")
    if user == config.APP_USERNAME and pwd == config.APP_PASSWORD:
        return jsonify({"status": "ok", "token": "authenticated_guard"}), 200
    return jsonify({"status": "error", "message": "Sai tài khoản hoặc mật khẩu"}), 401


@app.route("/api/login_pin", methods=["POST"])
def login_pin():
    """Đăng nhập bằng mã PIN khôi phục."""
    data = parse_request_payload()
    pin = data.get("pin", "")
    if pin == config.APP_RESET_PIN:
        return jsonify({"status": "ok", "token": "authenticated_guard"}), 200
    return jsonify({"status": "error", "message": "Mã PIN không chính xác"}), 401


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    print("=" * 60)
    print("[SERVER] HE THONG QUAN LY BAI GIU XE THONG MINH DANG KHOI DONG")
    print(f"[SERVER] Web Dashboard: http://localhost:{config.PORT}")
    print(f"[SERVER] Camera Index: {config.CAMERA_INDEX}")
    print(f"[SERVER] Database: {config.DB_TYPE.upper()}")
    print("=" * 60)
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)
