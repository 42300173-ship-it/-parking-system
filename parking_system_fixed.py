import math
import re
import sqlite3
import threading
import time
from datetime import datetime

import cv2
import easyocr
from flask import Flask, jsonify, request
import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st

print("=" * 60)
print("[CODE VERSION] parking_system_v6 - EXIT_CONFIRM + FREEZE + DEL_EXIT - build 2026-09-13")
print("=" * 60)

RATE_PER_MINUTE = 1000
PLATE_TTL_SEC = 180
RFID_DEBOUNCE_SEC = 3.0
_last_rfid_time = {}
DB_PATH = "parking_logs.db"
_db_lock = threading.Lock()

FULL_FMT = "%d/%m/%Y %H:%M:%S"
TIME_ONLY_FMT = "%H:%M:%S"

# Tai khoan dang nhap (don gian, hardcode cho do an)
APP_USERNAME = "admin"
APP_PASSWORD = "change-me"
APP_RESET_PIN = "change-me"


def db_connect():
  conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
  conn.execute("PRAGMA journal_mode=WAL")
  return conn


def now_full_str():
  return datetime.now().strftime(FULL_FMT)


def parse_dt(s):
  """Parse ca 2 dinh dang: full 'dd/mm/yyyy HH:MM:SS' (moi) va 'HH:MM:SS' (cu).
  Tra ve datetime hoac None."""
  if not s or s == "--:--:--":
    return None
  for fmt in (FULL_FMT, TIME_ONLY_FMT):
    try:
      dt = datetime.strptime(s, fmt)
      if fmt == TIME_ONLY_FMT:
        now = datetime.now()
        dt = now.replace(hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=0)
      return dt
    except Exception:
      continue
  return None


def calc_fee(time_in_str, time_out_str):
  t_in = parse_dt(time_in_str)
  t_out = parse_dt(time_out_str)
  if not t_in or not t_out:
    return 1000
  dur_sec = max(1, int((t_out - t_in).total_seconds()))
  mins = math.ceil(dur_sec / 60.0)
  return max(1000, mins * RATE_PER_MINUTE)


def set_valid_plate(plate_text, snapshot_rgb=None):
  del snapshot_rgb
  with _db_lock:
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pending_plate (id, plate_number, captured_at)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          plate_number = excluded.plate_number,
          captured_at = excluded.captured_at
        """,
        (plate_text, time.time()),
    )
    conn.commit()
    conn.close()


def get_valid_plate():
  with _db_lock:
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT plate_number, captured_at FROM pending_plate WHERE id = 1"
    )
    row = cursor.fetchone()
    conn.close()
  if not row:
    return "", None, 0.0
  return row[0] or "", None, float(row[1] or 0.0)


def clear_valid_plate():
  with _db_lock:
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE pending_plate SET plate_number = '', captured_at = 0 WHERE id = 1"
    )
    conn.commit()
    conn.close()


def init_db():
  conn = db_connect()
  cursor = conn.cursor()

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            slot_name TEXT,
            plate_number TEXT,
            rfid_uid TEXT
        )
    """)

  cursor.execute("PRAGMA table_info(logs)")
  columns_logs = [column[1] for column in cursor.fetchall()]
  if "slot_name" not in columns_logs:
    cursor.execute(
        "ALTER TABLE logs ADD COLUMN slot_name TEXT DEFAULT 'Khu Vuc Chung'"
    )
  if "rfid_uid" not in columns_logs:
    cursor.execute("ALTER TABLE logs ADD COLUMN rfid_uid TEXT DEFAULT ''")

  # Bang rieng cho LUOT XE RA (tach biet hoan toan voi bang logs xe vao)
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS exit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_name TEXT,
            plate_number TEXT,
            rfid_uid TEXT,
            time_in TEXT,
            time_out TEXT,
            fee INTEGER
        )
    """)

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS slot_status (
            slot_name TEXT PRIMARY KEY,
            status TEXT,
            time_in TEXT,
            time_out TEXT,
            last_fee INTEGER,
            current_plate TEXT,
            current_rfid TEXT
        )
    """)

  cursor.execute("PRAGMA table_info(slot_status)")
  columns_slots = [column[1] for column in cursor.fetchall()]
  if "time_out" not in columns_slots:
    cursor.execute("ALTER TABLE slot_status ADD COLUMN time_out TEXT DEFAULT ''")
  if "last_fee" not in columns_slots:
    cursor.execute(
        "ALTER TABLE slot_status ADD COLUMN last_fee INTEGER DEFAULT 0"
    )
  if "current_plate" not in columns_slots:
    cursor.execute(
        "ALTER TABLE slot_status ADD COLUMN current_plate TEXT DEFAULT ''"
    )
  if "current_rfid" not in columns_slots:
    cursor.execute(
        "ALTER TABLE slot_status ADD COLUMN current_rfid TEXT DEFAULT ''"
    )

  for slot in ["C1", "C2", "C3"]:
    cursor.execute(
        "INSERT OR IGNORE INTO slot_status (slot_name, status, time_in,"
        " time_out, last_fee, current_plate, current_rfid) VALUES (?, 'E',"
        " '', '', 0, '', '')",
        (slot,),
    )

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS revenue (
            id INTEGER PRIMARY KEY,
            total INTEGER
        )
    """)
  cursor.execute("INSERT OR IGNORE INTO revenue (id, total) VALUES (1, 0)")

  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_plate (
            id INTEGER PRIMARY KEY,
            plate_number TEXT,
            captured_at REAL
        )
    """)
  cursor.execute(
      "INSERT OR IGNORE INTO pending_plate (id, plate_number, captured_at)"
      " VALUES (1, '', 0)"
  )

  # Cho XE RA xac nhan tay: quet lan 2 chi tao yeu cau cho, bam nut moi ghi exit_logs
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_exit (
            slot_name TEXT PRIMARY KEY,
            plate_number TEXT,
            rfid_uid TEXT,
            time_in TEXT,
            requested_at TEXT
        )
    """)

  conn.commit()
  conn.close()


init_db()


def find_first_empty_slot():
  """BANG (RFID): tim vi tri RFID con trong dau tien C1 -> C2 -> C3.
  CHI dua vao current_rfid (the dang do), KHONG dua vao IR/status.
  Nhu vay quet xe dau tien sau khi xoa DB luon la C1."""
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("SELECT slot_name, current_rfid FROM slot_status")
  rows = {r[0]: (r[1] or "") for r in cursor.fetchall()}
  conn.close()
  for slot_name in ["C1", "C2", "C3"]:
    if not rows.get(slot_name):
      return slot_name
  return None


def find_slot_by_rfid(rfid_uid):
  """BANG (RFID): tim vi tri ma the nay DANG DO (current_rfid khop).
  KHONG dung status/IR -> IR do/xanh khong lam sai toggle vao/ra."""
  if not rfid_uid:
    return None
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT slot_name FROM slot_status WHERE current_rfid = ?",
      (rfid_uid,),
  )
  row = cursor.fetchone()
  conn.close()
  return row[0] if row else None


def ir_update_slot(slot, status):
  """O MAU (IR): chi doi mau xanh/do theo cam bien, KHONG dung DB bang.
  Khong ghi logs/exit_logs, khong tinh phi, khong xoa current_rfid."""
  if slot not in ["C1", "C2", "C3"]:
    return
  if status not in ["F", "E"]:
    return
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE slot_status SET status = ? WHERE slot_name = ?", (status, slot)
  )
  conn.commit()
  conn.close()
  print(f"[IR_UI] slot={slot} mau={'DO' if status == 'F' else 'XANH'} (chi doi mau)")


def rfid_entry(slot, plate_number, rfid_uid):
  """BANG (RFID) VAO: luu the + bien so + gio vao, KHONG doi mau IR."""
  now_full = now_full_str()
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE slot_status SET time_in = ?, current_plate = ?,"
      " current_rfid = ? WHERE slot_name = ?",
      (now_full, plate_number, rfid_uid, slot),
  )
  conn.commit()
  conn.close()


def rfid_exit(slot):
  """BANG (RFID) RA: tinh phi, ghi exit_logs, xoa the, KHONG doi mau IR.
  Tra ve (fee, time_in, time_out, plate, rfid)."""
  conn = db_connect()
  cursor = conn.cursor()
  now_full = now_full_str()
  cursor.execute(
      "SELECT time_in, current_plate, current_rfid FROM slot_status"
      " WHERE slot_name = ?",
      (slot,),
  )
  row = cursor.fetchone()
  old_time_in = row[0] if row else ""
  old_plate = row[1] if row else ""
  old_rfid = row[2] if row else ""
  fee = calc_fee(old_time_in, now_full) if old_time_in else 1000
  cursor.execute(
      "UPDATE slot_status SET time_out = ?, last_fee = ?,"
      " current_plate = '', current_rfid = '' WHERE slot_name = ?",
      (now_full, fee, slot),
  )
  cursor.execute("UPDATE revenue SET total = total + ? WHERE id = 1", (fee,))
  cursor.execute(
      "INSERT INTO exit_logs (slot_name, plate_number, rfid_uid,"
      " time_in, time_out, fee) VALUES (?, ?, ?, ?, ?, ?)",
      (slot, old_plate or "KHONG_XAC_DINH", old_rfid, old_time_in,
       now_full, fee),
  )
  conn.commit()
  conn.close()
  print(
      f"[RFID_EXIT_OK] slot={slot} plate={old_plate} rfid={old_rfid} fee={fee}"
  )
  return fee


def reset_ir_slots():
  """Dat lai 3 o IR ve TRONG (xanh) khi test. Khong xoa bang vao/ra."""
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("UPDATE slot_status SET status = 'E'")
  conn.commit()
  conn.close()


def request_exit_pending(slot):
  """Quet lan 2 chi tao yeu cau cho xac nhan, CHUA ghi exit_logs.
  Tra ve True neu tao moi, False neu da co yeu cau cho slot nay."""
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT time_in, current_plate, current_rfid FROM slot_status"
      " WHERE slot_name = ?",
      (slot,),
  )
  row = cursor.fetchone()
  if not row or not (row[2] or ""):
    conn.close()
    return False
  cursor.execute(
      """INSERT OR IGNORE INTO pending_exit
         (slot_name, plate_number, rfid_uid, time_in, requested_at)
         VALUES (?, ?, ?, ?, ?)""",
      (slot, row[1] or "", row[2] or "", row[0] or "", now_full_str()),
  )
  created = cursor.rowcount > 0
  conn.commit()
  conn.close()
  if created:
    print(f"[EXIT_PENDING] slot={slot} rfid={row[2]} doi bam Xac nhan")
  return created


def get_pending_exits():
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT slot_name, plate_number, rfid_uid, time_in, requested_at"
      " FROM pending_exit ORDER BY requested_at"
  )
  data = cursor.fetchall()
  conn.close()
  return data


def confirm_exit_pending(slot):
  """Ban bam 'Xac nhan XE RA' moi ghi exit_logs + tinh phi. Chi ghi 1 lan."""
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT slot_name FROM pending_exit WHERE slot_name = ?", (slot,)
  )
  if not cursor.fetchone():
    conn.close()
    return None
  cursor.execute("DELETE FROM pending_exit WHERE slot_name = ?", (slot,))
  conn.commit()
  conn.close()
  return rfid_exit(slot)


def cancel_exit_pending(slot):
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM pending_exit WHERE slot_name = ?", (slot,))
  conn.commit()
  conn.close()


def delete_exit_log_by_id(log_id):
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM exit_logs WHERE id = ?", (log_id,))
  conn.commit()
  conn.close()


def update_slot_in_db(slot, status, plate_number="", rfid_uid=""):
  """Giu lai de tuong thich code cu (sensor cu): chuyen ve IR-only."""
  return ir_update_slot(slot, status)


def get_slots_status():
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT slot_name, status, time_in, time_out, last_fee,"
      " current_plate, current_rfid FROM slot_status"
  )
  rows = cursor.fetchall()

  cursor.execute("SELECT total FROM revenue WHERE id = 1")
  rev_row = cursor.fetchone()
  total_rev = rev_row[0] if rev_row else 0
  conn.close()

  result = {"total_revenue": total_rev, "slots": {}}
  for r in rows:
    result["slots"][r[0]] = {
        "status": r[1],
        "time_in": r[2],
        "time_out": r[3],
        "last_fee": r[4],
        "current_plate": r[5] or "",
        "current_rfid": r[6] or "",
    }
  return result


def save_to_db(plate, slot="C1", rfid_uid=""):
  conn = db_connect()
  cursor = conn.cursor()
  now = datetime.now().strftime(FULL_FMT)
  cursor.execute(
      "INSERT INTO logs (timestamp, slot_name, plate_number, rfid_uid) VALUES"
      " (?, ?, ?, ?)",
      (now, slot, plate, rfid_uid),
  )
  conn.commit()
  conn.close()


def get_all_logs():
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, slot_name, timestamp, plate_number, rfid_uid FROM logs"
      " ORDER BY id DESC"
  )
  data = cursor.fetchall()
  conn.close()
  return data


def get_all_exit_logs():
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, slot_name, plate_number, rfid_uid, time_in, time_out, fee"
      " FROM exit_logs ORDER BY id DESC"
  )
  data = cursor.fetchall()
  conn.close()
  return data


def delete_log_by_id(log_id):
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM logs WHERE id = ?", (log_id,))
  conn.commit()
  conn.close()


def clear_all_logs():
  conn = db_connect()
  cursor = conn.cursor()
  cursor.execute("DELETE FROM logs")
  cursor.execute("DELETE FROM exit_logs")
  cursor.execute("DELETE FROM pending_exit")
  cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
  cursor.execute("DELETE FROM sqlite_sequence WHERE name='exit_logs'")
  cursor.execute("UPDATE revenue SET total = 0 WHERE id = 1")
  # Reset ca RFID (the dang do) lan IR (mau) ve trong de test lai tu C1
  cursor.execute(
      "UPDATE slot_status SET status = 'E', time_in = '', time_out = '',"
      " last_fee = 0, current_plate = '', current_rfid = ''"
  )
  conn.commit()
  conn.close()


@st.cache_resource
def load_ocr_reader():
  # Bat GPU (may co NVIDIA GPU) -> tang toc OCR dang ke so voi CPU.
  try:
    return easyocr.Reader(["en"], gpu=True)
  except Exception as e:
    print(f"Khong bat duoc GPU cho EasyOCR ({e}), dung lai CPU.")
    return easyocr.Reader(["en"], gpu=False)


def to_rgb(img_np):
  if img_np.ndim == 2:
    return cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
  if img_np.shape[2] == 4:
    return cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
  return img_np


def resize_for_ocr(img, target_width=400):
  """Resize anh ve chieu rong vua phai truoc khi OCR."""
  h, w = img.shape[:2]
  if w <= target_width:
    return img
  scale = target_width / float(w)
  return cv2.resize(img, (target_width, int(h * scale)))


def ocr_text(image_gray_or_rgb):
  small = resize_for_ocr(image_gray_or_rgb)
  results = reader.readtext(small)
  return "".join([res[1] + " " for res in results])


def pick_best_plate(*candidates):
  cleaned = [clean_plate_text(c) for c in candidates if c]
  for text in cleaned:
    if is_valid_plate_format(text):
      return text
  cleaned.sort(key=len, reverse=True)
  return cleaned[0] if cleaned else ""


def clean_plate_text(text):
  text = re.sub(r"\b(POWERSTAR|POWER|STAR|VIE|VIEE|VIE1|EV)\b", "", text.upper())
  text = re.sub(r"(\d{2}[A-Z])[ILil1]", r"\1 1", text)
  raw = re.sub(r"[^A-Z0-9]", "", text)

  if len(raw) < 6:
    return raw

  raw_list = list(raw)
  char_to_digit = {
      "B": "5",
      "S": "5",
      "Z": "2",
      "O": "0",
      "D": "0",
      "Q": "0",
      "G": "6",
  }
  if raw_list[0] in char_to_digit:
    raw_list[0] = char_to_digit[raw_list[0]]
  if raw_list[1] in char_to_digit:
    raw_list[1] = char_to_digit[raw_list[1]]
  raw = "".join(raw_list)

  match_bike = re.search(r"(\d{2})([A-Z])([0-9])(\d{4,5})", raw)
  if match_bike:
    prov, char, num, tail = match_bike.groups()
    if len(tail) == 5:
      return f"{prov}{char}{num}-{tail[:3]}.{tail[3:]}"
    return f"{prov}{char}{num}-{tail}"

  match_bike_missing_num = re.search(r"^(\d{2})([A-Z])(\d{5})$", raw)
  if match_bike_missing_num:
    prov, char, tail = match_bike_missing_num.groups()
    return f"{prov}{char}1-{tail[:3]}.{tail[3:]}"

  if len(raw) >= 7 and raw[:2].isdigit():
    if raw[0] == "6" and raw[1] == "1":
      raw = "51" + raw[2:]
    raw_list = list(raw)
    digit_to_char = {
        "1": "G",
        "7": "G",
        "6": "G",
        "0": "D",
        "8": "B",
        "5": "S",
        "2": "Z",
        "4": "A",
    }
    if raw_list[2] in digit_to_char:
      raw_list[2] = digit_to_char[raw_list[2]]
    raw = "".join(raw_list)

    if len(raw) == 9 and raw[3].isdigit():
      raw = raw[:3] + raw[4:]

    if len(raw) == 8:
      return f"{raw[:3]}-{raw[3:6]}.{raw[6:]}"
    elif len(raw) == 7:
      return f"{raw[:3]}-{raw[3:]}"

  return raw


VALID_PLATE_PATTERN = re.compile(
    r"^\d{2}[A-Z]\d?-\d{3}\.\d{2,3}$" r"|^\d{2}[A-Z]\d?-\d{4,5}$"
)


def is_valid_plate_format(text):
  return bool(VALID_PLATE_PATTERN.match(text or ""))


def detect_and_crop_plate(img_np):
  gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
  blur = cv2.GaussianBlur(gray, (5, 5), 0)
  edged = cv2.Canny(blur, 50, 200)

  contours, _ = cv2.findContours(
      edged.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
  )
  contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]

  plate_crop = gray
  bbox = None

  for c in contours:
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    if len(approx) == 4:
      x, y, w, h = cv2.boundingRect(c)
      aspect_ratio = w / float(h)

      if 0.8 <= aspect_ratio <= 5.5 and w > 60 and h > 20:
        y1, y2 = max(0, y - 8), min(gray.shape[0], y + h + 8)
        x1, x2 = max(0, x - 8), min(gray.shape[1], x + w + 8)
        plate_crop = gray[y1:y2, x1:x2]
        bbox = (x1, y1, x2, y2)

        if aspect_ratio < 1.7:
          h_c, w_c = plate_crop.shape
          mid_h = int(h_c * 0.48)
          top_half = plate_crop[0:mid_h, :]
          bottom_half = plate_crop[mid_h:h_c, :]

          target_h = max(top_half.shape[0], bottom_half.shape[0])
          top_half = cv2.resize(
              top_half,
              (
                  int(top_half.shape[1] * (target_h / top_half.shape[0])),
                  target_h,
              ),
          )
          bottom_half = cv2.resize(
              bottom_half,
              (
                  int(
                      bottom_half.shape[1] * (target_h / bottom_half.shape[0])
                  ),
                  target_h,
              ),
          )

          plate_crop = np.hstack((top_half, bottom_half))
        break

  return plate_crop, bbox is not None, bbox


# =====================================================
# FLASK SERVER
# =====================================================
flask_app = Flask(__name__)


@flask_app.after_request
def add_cors(response):
  response.headers["Access-Control-Allow-Origin"] = "*"
  response.headers["Access-Control-Allow-Headers"] = "Content-Type"
  response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
  return response


def parse_request_payload():
  return request.get_json(silent=True) or request.form.to_dict() or {}


@flask_app.route("/api/update_slot", methods=["POST", "GET"])
def update_slot():
  """O MAU (IR): ESP32 gui slot=C1/C2/C3 + status=F (co vat) / E (trong).
  CHI doi mau xanh/do, KHONG tao du lieu bang, KHONG tinh phi.
  Bang vao/ra CHI tu /api/rfid_scan."""
  if request.method == "GET":
    return jsonify({"message": "Server Flask dang hoat dong!"}), 200

  data = parse_request_payload()
  slot = data.get("slot")
  status = data.get("status")
  ir_update_slot(slot, status)
  return jsonify({"status": "ir_ok", "slot": slot, "ir": status}), 200


@flask_app.route("/api/rfid_scan", methods=["POST"])
def rfid_scan():
  """BANG (RFID) - khong dung IR, co xac nhan tay khi RA:
  - The LA -> XE VAO ngay: gan C1 -> C2 -> C3, ghi logs. KHONG doi mau IR.
  - The TRUNG (quet lan 2) -> chi tao PENDING, doi ban bam 'Xac nhan XE RA'
    tren web moi ghi exit_logs. Nhu vay bang ra khong tu chay moi giay.
  """
  data = parse_request_payload()
  rfid_uid = data.get("rfid_uid") or data.get("uid") or "UNKNOWN"

  now_ts = time.time()
  last_ts = _last_rfid_time.get(rfid_uid, 0)
  if now_ts - last_ts < RFID_DEBOUNCE_SEC:
    print(f"[RFID_DEBOUNCE] Bo qua scan lap trong 3s: {rfid_uid}")
    return jsonify({"status": "duplicate_ignored", "rfid_uid": rfid_uid}), 200
  _last_rfid_time[rfid_uid] = now_ts

  # 1) Kiem tra XE RA truoc: the nay co dang do trong bai khong?
  existing_slot = find_slot_by_rfid(rfid_uid)
  if existing_slot is not None:
    request_exit_pending(existing_slot)
    print(
        f"[RFID_EXIT_PENDING] The {rfid_uid} quet lan 2 -> doi xac nhan"
        f" tai {existing_slot}"
    )
    return (
        jsonify(
            {
                "status": "exit_pending",
                "action": "exit_pending",
                "rfid_uid": rfid_uid,
                "slot": existing_slot,
            }
        ),
        200,
    )

  # 2) The la -> XE VAO: chon vi tri trong dau tien C1 -> C2 -> C3
  slot = find_first_empty_slot()
  if slot is None:
    print("[RFID_SCAN] BAI DA DAY - tu choi quet the.")
    return (
        jsonify({"status": "parking_full", "message": "Bai da day"}),
        200,
    )

  plate_text, _snapshot, last_valid_time = get_valid_plate()
  age_sec = time.time() - last_valid_time if last_valid_time else None
  plate_ok = (
      bool(plate_text)
      and plate_text != "KHONG_XAC_DINH"
      and age_sec is not None
      and age_sec <= PLATE_TTL_SEC
  )

  if plate_ok:
    print(
        f"[RFID_ENTRY] The MOI {rfid_uid} -> XE VAO tai {slot} voi bien"
        f" {plate_text} (cach {age_sec:.1f}s)"
    )
    clear_valid_plate()
  else:
    plate_text = "KHONG_XAC_DINH"
    print(
        "[RFID_ENTRY] Khong co bien so hop le trong bo dem."
        f" Luu {rfid_uid} voi KHONG_XAC_DINH tai vi tri {slot}"
    )

  save_to_db(plate_text, slot, rfid_uid)
  rfid_entry(slot, plate_number=plate_text, rfid_uid=rfid_uid)

  return (
      jsonify(
          {
              "status": "entry",
              "action": "entry",
              "rfid_uid": rfid_uid,
              "slot": slot,
              "plate": plate_text,
          }
      ),
      200,
  )


def run_flask():
  flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


if not any(thread.name == "FlaskThread" for thread in threading.enumerate()):
  _reset_conn = db_connect()
  _reset_conn.execute("UPDATE revenue SET total = 0 WHERE id = 1")
  _reset_conn.commit()
  _reset_conn.close()
  print("[KHOI DONG] Da reset Tong chi phi ve 0.")

  t = threading.Thread(target=run_flask, name="FlaskThread", daemon=True)
  t.start()


# =====================================================
# STREAMLIT UI
# =====================================================
st.set_page_config(
    page_title="He Thong Quan Ly Bai Do Xe Thong Minh",
    page_icon="🚗",
    layout="wide",
)

reader = load_ocr_reader()

st.markdown(
    """
    <meta name="google" content="notranslate">
    <style>
    [data-testid="stTable"] *, [data-testid="stDataFrame"] * { text-align: center !important; }
    div[data-testid="stDataFrame"] div[role="columnheader"] { justify-content: center !important; }
    div[data-testid="stDataFrame"] div[role="cell"] { justify-content: center !important; }
    </style>
""",
    unsafe_allow_html=True,
)

# =====================================================
# MAN HINH DANG NHAP
# =====================================================
if "authenticated" not in st.session_state:
  st.session_state.authenticated = False
if "show_forgot" not in st.session_state:
  st.session_state.show_forgot = False

if not st.session_state.authenticated:
  st.markdown(
      """
      <h2 style='text-align: center; color: #1E88E5;'>
          🔒 Dang Nhap He Thong Bai Do Xe
      </h2>
  """,
      unsafe_allow_html=True,
  )

  _, mid_col, _ = st.columns([1, 1.2, 1])
  with mid_col:
    username = st.text_input("Tai khoan", key="login_username")
    password = st.text_input(
        "Mat khau", type="password", key="login_password"
    )

    if st.button("Dang nhap", use_container_width=True, type="primary"):
      if username == APP_USERNAME and password == APP_PASSWORD:
        st.session_state.authenticated = True
        st.rerun()
      else:
        st.error("Sai tai khoan hoac mat khau.")

    if st.button("Ban khong nho mat khau?", use_container_width=True):
      st.session_state.show_forgot = not st.session_state.show_forgot

    if st.session_state.show_forgot:
      pin = st.text_input(
          "Nhap ma PIN khoi phuc", type="password", key="reset_pin"
      )
      if st.button("Xac nhan ma PIN", use_container_width=True):
        if pin == APP_RESET_PIN:
          st.session_state.authenticated = True
          st.rerun()
        else:
          st.error("Ma PIN khong dung.")

  st.stop()

with st.sidebar:
  if st.button("🚪 Dang xuat"):
    st.session_state.authenticated = False
    st.rerun()

st.markdown(
    """
    <h1 style='text-align: center; color: #1E88E5; font-size: 36px; font-weight: bold;'>
        🚗 HE THONG QUAN LY BAI DO XE TONG HOP
    </h1>
""",
    unsafe_allow_html=True,
)


@st.fragment(run_every=1)
def render_realtime_slots():
  # TACH RIENG: mau xanh/do = IR (status), noi dung bang = RFID (current_rfid).
  data = get_slots_status()
  slots_data = data["slots"]

  now_dt = datetime.now()

  # Tong phi: chi o DO (IR=F) moi tinh tam theo gio thuc (chay),
  # o XANH (IR=E) lay last_fee dung yen -> xanh khong bao gio chay.
  display_total_revenue = 0
  live_fees = {}
  for slot_name, s_info in slots_data.items():
    if s_info.get("status") == "F" and s_info["time_in"]:
      t_in = parse_dt(s_info["time_in"])
      if t_in:
        dur = max(0, int((now_dt - t_in).total_seconds()))
        mins = math.ceil(dur / 60.0) if dur > 0 else 1
        fee = max(1000, mins * RATE_PER_MINUTE)
      else:
        fee = 1000
      live_fees[slot_name] = fee
      display_total_revenue += fee
    else:
      live_fees[slot_name] = s_info.get("last_fee") or 0
      display_total_revenue += s_info.get("last_fee") or 0

  st.markdown(
      f"""
        <div style="background: #1e293b; color: white; padding: 15px 25px; border-radius: 12px; text-align: center; margin-bottom: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <div style="font-size: 16px; color: #94a3b8; font-weight: 500;">💰 TONG CHI PHI THU DUOC CUA BAI XE</div>
            <div style="font-size: 28px; color: #4ade80; font-weight: bold; margin-top: 5px;">{display_total_revenue:,} VND</div>
        </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("### 🅿️ Trang Thai Cac Vi Tri Do Xe (Mau theo cam bien IR)")
  c_reset1, c_reset2 = st.columns([3, 1])
  with c_reset2:
    if st.button("Reset 3 o IR ve XANH", key="btn_reset_ir"):
      reset_ir_slots()
      st.toast("Da reset 3 o IR ve TRONG (xanh). Quet RFID lai tu C1.")
      st.rerun()
  col_c1, col_c2, col_c3 = st.columns(3)

  card_full_style = "background-color: #e74c3c; color: white; padding: 18px; border-radius: 12px; text-align: left; font-weight: bold; box-shadow: 0 4px 12px rgba(231, 76, 60, 0.4); margin-bottom: 10px;"
  card_empty_style = "background-color: #2ecc71; color: white; padding: 18px; border-radius: 12px; text-align: left; font-weight: bold; box-shadow: 0 4px 12px rgba(46, 204, 113, 0.4); margin-bottom: 10px;"
  title_style = "font-size: 18px; font-weight: bold; margin-bottom: 10px; border-bottom: 2px solid rgba(255,255,255,0.4); padding-bottom: 6px; text-align: center;"
  detail_style = "font-size: 14px; font-weight: normal; margin-top: 6px;"
  highlight_style = "font-weight: bold; color: #ffeb3b;"

  for col, slot_name in zip([col_c1, col_c2, col_c3], ["C1", "C2", "C3"]):
    with col:
      info = slots_data.get(
          slot_name,
          {"status": "E", "time_in": "", "time_out": "", "last_fee": 0,
           "current_plate": "", "current_rfid": ""},
      )
      # MAU theo IR: F = DO (co vat) -> CHAY, E = XANH (trong) -> DUNG YEN
      is_red = (info.get("status") == "F")
      card_style = card_full_style if is_red else card_empty_style
      ir_label = "CO XE (IR)" if is_red else "TRONG (IR)"
      plate = info.get("current_plate") or ""
      if is_red:
        # O DO: chay thoi gian do + phi tam tinh. Bo dong 'The dang do'.
        t_in_str = info["time_in"] if info["time_in"] else "--:--:--"
        t_in = parse_dt(info["time_in"]) if info["time_in"] else None
        dur_sec = max(0, int((now_dt - t_in).total_seconds())) if t_in else 0
        dur_min, dur_rem_sec = dur_sec // 60, dur_sec % 60
        dur_str = f"{dur_min} phut {dur_rem_sec} giay"
        fee = live_fees.get(slot_name, 1000)
        plate_line = (
            f'<div style="{detail_style}">🔢 Bien so: {plate}</div>'
            if plate else ""
        )
        st.markdown(
            f"""
                    <div style="{card_style}">
                        <div style="{title_style}">VI TRI {slot_name}: {ir_label}</div>
                        {plate_line}
                        <div style="{detail_style}">🕒 Thoi gian vao: {t_in_str}</div>
                        <div style="{detail_style}">⏱️ Thoi gian do: {dur_str}</div>
                        <div style="{detail_style}">💵 Phi tam tinh: <span style="{highlight_style}">{fee:,} VND</span></div>
                    </div>
                """,
            unsafe_allow_html=True,
        )
      else:
        # O XANH: dung yen hoan toan, khong chay gi ca
        t_in_str = info["time_in"] if info["time_in"] else "--:--:--"
        t_out_str = info["time_out"] if info["time_out"] else "--:--:--"
        last_fee = info["last_fee"]
        st.markdown(
            f"""
                    <div style="{card_style}">
                        <div style="{title_style}">VI TRI {slot_name}: {ir_label}</div>
                        <div style="{detail_style}">⏮️ Luot truoc vao: {t_in_str}</div>
                        <div style="{detail_style}">⏭️ Luot truoc ra: {t_out_str}</div>
                        <div style="{detail_style}">💰 Tong phi luot truoc: <span style="{highlight_style}">{last_fee:,} VND</span></div>
                    </div>
                """,
            unsafe_allow_html=True,
        )


render_realtime_slots()

st.write("---")

@st.fragment(run_every=1)
def render_pending_plate():
  plate_text, _, captured_at = get_valid_plate()
  age_sec = time.time() - captured_at if captured_at else None
  still_valid = (
      bool(plate_text)
      and plate_text != "KHONG_XAC_DINH"
      and age_sec is not None
      and age_sec <= PLATE_TTL_SEC
  )
  if still_valid:
    remain = int(PLATE_TTL_SEC - age_sec)
    st.success(
        f"Bien so san sang ghep RFID: **{plate_text}** "
        f"(con {remain}s). Quet the ngay."
    )
  else:
    st.warning(
        "Chua co bien so hop le trong bo dem. "
        "Hay chup/tai anh bien so (hoac nhap tay) **truoc**, roi moi quet RFID."
    )


render_pending_plate()

st.write("---")

# =====================================================
# CAMERA & NHAN DIEN BIEN SO
# =====================================================
st.markdown("### 📷 Nhan Dien & Luu Bien So Xe")
st.caption(
    "BANG theo RFID: the LA = VAO (C1->C2->C3 theo the trong), "
    "quet lai CUNG the = RA. "
    "MAU 3 o theo IR tu ESP32 (/api/update_slot)."
)
option = st.segmented_control(
    "Phuong thuc nhap anh:",
    options=["Chup qua Camera", "Tai file anh"],
    default="Chup qua Camera",
    required=True,
    width="stretch",
)

input_image = None
if option == "Chup qua Camera":
  input_image = st.camera_input(
      "Dua bien so truoc camera va bam chup",
      resolution="720p",
  )
else:
  input_image = st.file_uploader(
      "Chon file anh bien so:", type=["jpg", "jpeg", "png"]
  )

manual_plate = st.text_input(
    "Nhap bien so thu cong neu OCR sai (vi du 51A-123.45):",
    placeholder="51A-123.45",
)
if st.button("Gan bien so thu cong vao bo dem RFID"):
  typed = clean_plate_text(manual_plate.strip().upper())
  if typed:
    set_valid_plate(typed)
    st.toast(f"Da gan bien {typed}. Co the quet RFID.")
    st.rerun()
  else:
    st.error("Chua nhap bien so.")

if input_image is not None:
  t_start = time.time()
  image = Image.open(input_image)
  img_array = to_rgb(np.array(image))

  h_img, w_img = img_array.shape[:2]
  x_start, x_end = int(w_img * 0.20), int(w_img * 0.80)
  y_start, y_end = int(h_img * 0.25), int(h_img * 0.75)
  aim_crop = img_array[y_start:y_end, x_start:x_end]

  img_preview_box = img_array.copy()
  cv2.rectangle(
      img_preview_box, (x_start, y_start), (x_end, y_end), (0, 255, 0), 3
  )
  cv2.putText(
      img_preview_box,
      "DAT BIEN SO VAO KHUNG NAY",
      (x_start, max(25, y_start - 10)),
      cv2.FONT_HERSHEY_SIMPLEX,
      0.7,
      (0, 255, 0),
      2,
  )

  col1, col2 = st.columns(2)
  with col1:
    st.image(
        img_preview_box,
        width="stretch",
        caption="Anh vua chup (khung ngam)",
    )

  with col2:
    with st.spinner("Dang nhan dien..."):
      cropped_plate, found, bbox = detect_and_crop_plate(img_array)

      primary_crop = cropped_plate if found else aim_crop
      primary_text = ocr_text(primary_crop)
      cleaned_text = clean_plate_text(primary_text)

      if not is_valid_plate_format(cleaned_text):
        fallback_crop = aim_crop if found else cropped_plate
        fallback_text = ocr_text(fallback_crop)
        cleaned_text = pick_best_plate(primary_text, fallback_text)

      preview_crop = cropped_plate if found else aim_crop
      st.image(preview_crop, width=280, caption="Vung gui OCR")

      elapsed = time.time() - t_start
      st.caption(f"⏱️ Thoi gian xu ly: {elapsed:.1f}s")

      if cleaned_text:
        set_valid_plate(cleaned_text, img_preview_box)
        if is_valid_plate_format(cleaned_text):
          st.success(f"BIEN SO XE: {cleaned_text}")
        else:
          st.warning(
              f"OCR ra: {cleaned_text} (dinh dang chua chuan). "
              "Sua bang o nhap thu cong phia tren neu sai."
          )

        # Canh bao DO: neu bien so se luu la KHONG_XAC_DINH thi moi nhap lai
        if (not cleaned_text or cleaned_text == "KHONG_XAC_DINH"
            or not is_valid_plate_format(cleaned_text)):
          st.error(
              "⚠️ Bien so KHONG_XAC_DINH! Neu quet the luc nay se luu"
              " KHONG_XAC_DINH. Vui long chup lai / nhap tay lai bien so"
              " truoc khi quet RFID."
          )
        if st.button("Luu thu cong (khong can RFID)", width="stretch"):
          auto_slot = find_first_empty_slot()
          if auto_slot is None:
            st.error("Bai da day, khong con vi tri trong.")
          else:
            manual_uid = f"THU_CONG_{datetime.now().strftime('%H%M%S')}"
            save_to_db(cleaned_text, auto_slot, rfid_uid=manual_uid)
            rfid_entry(auto_slot, plate_number=cleaned_text, rfid_uid=manual_uid)
            clear_valid_plate()
            st.toast(f"Da luu xe {cleaned_text} vao vi tri {auto_slot}!")
            st.rerun()
      else:
        st.error(
            "Khong doc duoc bien so. Chup gan hon, du sang, "
            "bien nam trong khung xanh — hoac nhap tay."
        )

st.write("---")

# =====================================================
# CHO XAC NHAN XE RA (fix spam moi giay + dung yen gio)
# Quet the lan 2 chi tao PENDING. Ban bam Xac nhan moi ghi vao bang ra.
# IR khong bao gio ghi vao bang nay.
# Dung fragment tu refresh moi 2s -> quet RFID la hien ngay,
# khong can bam Take/Clear photo moi thay.
# =====================================================
@st.fragment(run_every=2)
def render_pending_exit():
  st.markdown("### ✅ Xac nhan XE RA (quet lan 2 -> bam nut moi ra bang)")
  pendings = get_pending_exits()
  if pendings:
    for slot_p, plate_p, rfid_p, time_in_p, req_at in pendings:
      c1, c2, c3 = st.columns([2, 1, 1])
      with c1:
        st.warning(
            f"Xe **{plate_p}** / the **{rfid_p}** tai **{slot_p}**"
            f" (vao: {time_in_p}) muon RA. Bam xac nhan de ghi bang."
        )
      with c2:
        if st.button(f"Xac nhan {slot_p} RA", key=f"btn_confirm_{slot_p}"):
          fee = confirm_exit_pending(slot_p)
          st.toast(f"Da cho {slot_p} RA, phi {fee:,} VND.")
          st.rerun()
      with c3:
        if st.button(f"Huy {slot_p}", key=f"btn_cancel_{slot_p}"):
          cancel_exit_pending(slot_p)
          st.rerun()
  else:
    st.caption("Khong co yeu cau ra nao dang cho. Quet the lan 2 se hien o day.")


render_pending_exit()

st.write("---")

# =====================================================
# 2 BANG RIENG: XE VAO / XE RA (giong nhau + cot phi)
# =====================================================
tab_in, tab_out = st.tabs(["🚗 Bang Xe Vao", "🅿️ Bang Xe Ra"])

with tab_in:
  @st.fragment(run_every=5)
  def render_logs_in():
    logs = get_all_logs()
    if logs:
      df = pd.DataFrame(
          logs,
          columns=[
              "STT (ID)",
              "Vi Tri Do",
              "Thoi Gian Vao",
              "Bien So Xe",
              "Ma The RFID",
          ],
      )
      st.dataframe(df, width="stretch", hide_index=True)

      c_del1, c_del2 = st.columns([2, 1])
      with c_del1:
        log_ids = [row[0] for row in logs]
        sel_id = st.selectbox("Chon STT muon xoa:", log_ids, key="sel_del_in")
        if st.button("Xoa dong da chon", key="btn_del_in"):
          delete_log_by_id(sel_id)
          st.rerun()

      with c_del2:
        if st.button("Xoa toan bo database", key="btn_clear_all"):
          clear_all_logs()
          clear_valid_plate()
          st.rerun()
    else:
      st.info("Chua co luot xe nao vao bai.")

  render_logs_in()

with tab_out:
  @st.fragment(run_every=5)
  def render_logs_out():
    exit_logs = get_all_exit_logs()
    if exit_logs:
      # Giong he bang vao: Thoi gian (ngay+gio) / Vi tri / Bien so / RFID + Phi
      df_out = pd.DataFrame(
          exit_logs,
          columns=[
              "STT (ID)",
              "Vi Tri Do",
              "Bien So Xe",
              "Ma The RFID",
              "Thoi Gian Vao",
              "Thoi Gian Ra",
              "Phi Gui Xe (VND)",
          ],
      )
      st.dataframe(df_out, width="stretch", hide_index=True)

      c_del1, c_del2 = st.columns([2, 1])
      with c_del1:
        exit_ids = [row[0] for row in exit_logs]
        sel_exit = st.selectbox(
            "Chon STT muon xoa:", exit_ids, key="sel_del_out"
        )
        if st.button("Xoa dong da chon", key="btn_del_out"):
          delete_exit_log_by_id(sel_exit)
          st.rerun()
      with c_del2:
        if st.button("Xoa toan bo database", key="btn_clear_out"):
          clear_all_logs()
          clear_valid_plate()
          st.rerun()
    else:
      st.info("Chua co luot xe nao ra khoi bai.")

  render_logs_out()
