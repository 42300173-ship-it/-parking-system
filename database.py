import math
import os
import sqlite3
import threading
import time
from datetime import datetime
import config

try:
  import pymysql
  from pymysql.cursors import DictCursor
  PYMYSQL_AVAILABLE = True
except ImportError:
  PYMYSQL_AVAILABLE = False

_db_lock = threading.Lock()
FULL_FMT = "%d/%m/%Y %H:%M:%S"
TIME_ONLY_FMT = "%H:%M:%S"


def now_full_str():
  return datetime.now().strftime(FULL_FMT)


def parse_dt(s):
  """Parse ca 2 dinh dang: full 'dd/mm/yyyy HH:MM:SS' va 'HH:MM:SS'."""
  if not s or s == "--:--:--":
    return None
  for fmt in (FULL_FMT, TIME_ONLY_FMT):
    try:
      dt = datetime.strptime(s, fmt)
      if fmt == TIME_ONLY_FMT:
        now = datetime.now()
        dt = now.replace(
            hour=dt.hour, minute=dt.minute, second=dt.second, microsecond=0
        )
      return dt
    except Exception:
      continue
  return None


def calc_fee(time_in_str, time_out_str=None):
  """Tinh tien gui xe dua tren so phut do."""
  t_in = parse_dt(time_in_str)
  if not t_in:
    return config.RATE_PER_MINUTE
  t_out = parse_dt(time_out_str) if time_out_str else datetime.now()
  if not t_out:
    return config.RATE_PER_MINUTE

  dur_sec = max(1, int((t_out - t_in).total_seconds()))
  mins = math.ceil(dur_sec / 60.0)
  return max(config.RATE_PER_MINUTE, mins * config.RATE_PER_MINUTE)


class DatabaseManager:

  def __init__(self):
    self.db_type = config.DB_TYPE
    if self.db_type == "mysql" and not PYMYSQL_AVAILABLE:
      print("[DB WARNING] PyMySQL chua cai dat, chuyen sang dung SQLite.")
      self.db_type = "sqlite"

  def get_connection(self):
    """Ket noi CSDL SQLite hoac MySQL."""
    if self.db_type == "mysql":
      try:
        conn = pymysql.connect(
            host=config.MYSQL_HOST,
            port=config.MYSQL_PORT,
            user=config.MYSQL_USER,
            password=config.MYSQL_PASSWORD,
            database=config.MYSQL_DB,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=DictCursor,
        )
        return conn, "mysql"
      except Exception as e:
        # Không được âm thầm chuyển sang SQLite: việc đó làm giao diện đọc
        # một CSDL khác và khiến người dùng tưởng dữ liệu MySQL bị sai/mất.
        raise RuntimeError(
            f"Không thể kết nối MySQL tại {config.MYSQL_HOST}:{config.MYSQL_PORT}/"
            f"{config.MYSQL_DB}: {e}"
        ) from e

    # SQLite fallback
    conn = sqlite3.connect(
        config.SQLITE_PATH, check_same_thread=False, timeout=10
    )
    conn.execute("PRAGMA journal_mode=WAL")
    return conn, "sqlite"

  def init_db(self):
    """Khoi tao cac bang neu chua ton tai."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()

      if db_type == "sqlite":
        # 1. Logs (Xe vao)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        slot_name TEXT,
                        plate_number TEXT,
                        rfid_uid TEXT,
                        image_path TEXT DEFAULT ''
                    )
                """)
        # 2. Exit logs (Xe ra)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS exit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        slot_name TEXT,
                        plate_number TEXT,
                        rfid_uid TEXT,
                        time_in TEXT,
                        time_out TEXT,
                        fee INTEGER,
                        image_path TEXT DEFAULT ''
                    )
                """)
        # 3. Slot status
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS slot_status (
                        slot_name TEXT PRIMARY KEY,
                        status TEXT DEFAULT 'E',
                        time_in TEXT DEFAULT '',
                        time_out TEXT DEFAULT '',
                        last_fee INTEGER DEFAULT 0,
                        current_plate TEXT DEFAULT '',
                        current_rfid TEXT DEFAULT '',
                        image_path TEXT DEFAULT ''
                    )
                """)
        # 4. Revenue
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS revenue (
                        id INTEGER PRIMARY KEY,
                        total INTEGER DEFAULT 0
                    )
                """)
        # 5. Pending exit (Quet the lan 2 cho xac nhan)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_exit (
                        slot_name TEXT PRIMARY KEY,
                        plate_number TEXT,
                        rfid_uid TEXT,
                        time_in TEXT,
                        requested_at TEXT,
                        fee_estimate INTEGER DEFAULT 0,
                        image_path TEXT DEFAULT ''
                    )
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_entry (
                        slot_name TEXT PRIMARY KEY,
                        plate_number TEXT,
                        rfid_uid TEXT,
                        requested_at TEXT,
                        image_path TEXT DEFAULT ''
                    )
                """)

        # Tu dong cap nhat cot cho cac bang SQLite neu da tao tu truoc do
        for tbl in ["logs", "exit_logs", "slot_status", "pending_exit", "pending_entry"]:
          cursor.execute(f"PRAGMA table_info({tbl})")
          cols = [c[1] for c in cursor.fetchall()]
          if "image_path" not in cols:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN image_path TEXT DEFAULT ''")
          if tbl == "pending_exit" and "fee_estimate" not in cols:
            cursor.execute(f"ALTER TABLE {tbl} ADD COLUMN fee_estimate INTEGER DEFAULT 0")

        for slot in ["C1", "C2", "C3"]:
          cursor.execute(
              "INSERT OR IGNORE INTO slot_status (slot_name, status, time_in,"
              " time_out, last_fee, current_plate, current_rfid, image_path)"
              " VALUES (?, 'E', '', '', 0, '', '', '')",
              (slot,),
          )
        cursor.execute(
            "INSERT OR IGNORE INTO revenue (id, total) VALUES (1, 0)"
        )
        conn.commit()

      else:
        # MySQL tables
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `logs` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `timestamp` VARCHAR(50) NOT NULL,
                        `slot_name` VARCHAR(20) DEFAULT 'C1',
                        `plate_number` VARCHAR(50) DEFAULT 'KHONG_XAC_DINH',
                        `rfid_uid` VARCHAR(50) DEFAULT '',
                        `image_path` VARCHAR(255) DEFAULT '',
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `exit_logs` (
                        `id` INT AUTO_INCREMENT PRIMARY KEY,
                        `slot_name` VARCHAR(20) DEFAULT 'C1',
                        `plate_number` VARCHAR(50) DEFAULT 'KHONG_XAC_DINH',
                        `rfid_uid` VARCHAR(50) DEFAULT '',
                        `time_in` VARCHAR(50) NOT NULL,
                        `time_out` VARCHAR(50) NOT NULL,
                        `fee` INT DEFAULT 0,
                        `image_path` VARCHAR(255) DEFAULT '',
                        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `slot_status` (
                        `slot_name` VARCHAR(10) PRIMARY KEY,
                        `status` VARCHAR(5) DEFAULT 'E',
                        `time_in` VARCHAR(50) DEFAULT '',
                        `time_out` VARCHAR(50) DEFAULT '',
                        `last_fee` INT DEFAULT 0,
                        `current_plate` VARCHAR(50) DEFAULT '',
                        `current_rfid` VARCHAR(50) DEFAULT '',
                        `image_path` VARCHAR(255) DEFAULT ''
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `revenue` (
                        `id` INT PRIMARY KEY,
                        `total` BIGINT DEFAULT 0
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `pending_exit` (
                        `slot_name` VARCHAR(10) PRIMARY KEY,
                        `plate_number` VARCHAR(50) DEFAULT '',
                        `rfid_uid` VARCHAR(50) DEFAULT '',
                        `time_in` VARCHAR(50) DEFAULT '',
                        `requested_at` VARCHAR(50) DEFAULT '',
                        `fee_estimate` INT DEFAULT 0,
                        `image_path` VARCHAR(255) DEFAULT ''
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS `pending_entry` (
                        `slot_name` VARCHAR(10) PRIMARY KEY,
                        `plate_number` VARCHAR(50) NOT NULL,
                        `rfid_uid` VARCHAR(50) NOT NULL,
                        `requested_at` VARCHAR(50) NOT NULL,
                        `image_path` VARCHAR(255) DEFAULT ''
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
                """)
        cursor.execute("DROP VIEW IF EXISTS `logs_daily_report`")
        cursor.execute("DROP VIEW IF EXISTS `exit_logs_daily_report`")
        cursor.execute("""
                    CREATE OR REPLACE VIEW `daily_report` AS
                    WITH RECURSIVE
                    events AS (
                        SELECT STR_TO_DATE(`timestamp`, '%d/%m/%Y %H:%i:%s') AS `event_date`,
                               0 AS `fee`
                        FROM `logs`
                        UNION ALL
                        SELECT STR_TO_DATE(`time_in`, '%d/%m/%Y %H:%i:%s'),
                               `fee`
                        FROM `exit_logs`
                    ),
                    bounds AS (
                        SELECT MIN(DATE(`event_date`)) AS `first_day`,
                               MAX(DATE(`event_date`)) AS `last_day`
                        FROM events
                    ),
                    calendar AS (
                        SELECT `first_day` AS `day`
                        FROM bounds
                        WHERE `first_day` IS NOT NULL
                        UNION ALL
                        SELECT DATE_ADD(`day`, INTERVAL 1 DAY)
                        FROM calendar
                        JOIN bounds ON 1 = 1
                        WHERE `day` < `last_day`
                    ),
                    totals AS (
                        SELECT DATE(`event_date`) AS `day`,
                               COUNT(*) AS `event_count`,
                               COALESCE(SUM(`fee`), 0) AS `total_fee`
                        FROM events
                        GROUP BY DATE(`event_date`)
                    )
                    SELECT DATE_FORMAT(calendar.`day`, '%d/%m/%Y') AS `ngay`,
                           CASE WHEN COALESCE(totals.`event_count`, 0) = 0
                                THEN 'KHONG CO DU LIEU'
                                ELSE 'TONG'
                           END AS `thong_bao`,
                           COALESCE(totals.`event_count`, 0) AS `tong_luot_ra_vao`,
                           COALESCE(totals.`total_fee`, 0) AS `tong_doanh_thu`
                    FROM calendar
                    LEFT JOIN totals ON totals.`day` = calendar.`day`
                """)
        for slot in ["C1", "C2", "C3"]:
          cursor.execute(
              "INSERT IGNORE INTO `slot_status` (`slot_name`, `status`)"
              " VALUES (%s, 'E')",
              (slot,),
          )
        cursor.execute(
            "INSERT IGNORE INTO `revenue` (`id`, `total`) VALUES (1, 0)"
        )

      conn.close()
      print(f"[DB INIT] Khoi tao thanh cong voi {db_type.upper()}.")

  def ir_update_slot(self, slot, status):
    """Cảm biến IR từ ESP32: F = có xe (đỏ), E = trống (xanh)."""
    if slot not in ["C1", "C2", "C3"] or status not in ["F", "E"]:
      return
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      param_mark = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          f"UPDATE slot_status SET status = {param_mark} WHERE slot_name ="
          f" {param_mark}",
          (status, slot),
      )
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def reset_slots(self):
    """Reset trạng thái hiện tại và các yêu cầu chờ, không xóa lịch sử."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("""
          UPDATE slot_status SET status = 'E', time_in = '', time_out = '',
          last_fee = 0, current_plate = '', current_rfid = '', image_path = ''
      """)
      cursor.execute("DELETE FROM pending_entry")
      cursor.execute("DELETE FROM pending_exit")
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def find_first_empty_slot(self):
    """Tìm vị trí trống đầu tiên C1 -> C2 -> C3 chưa có thẻ RFID đỗ."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("SELECT slot_name, current_rfid FROM slot_status")
      rows = cursor.fetchall()
      cursor.execute("SELECT slot_name FROM pending_entry")
      pending_rows = cursor.fetchall()
      conn.close()

    occupied = {}
    if db_type == "mysql":
      for r in rows:
        occupied[r["slot_name"]] = r["current_rfid"] or ""
    else:
      for r in rows:
        occupied[r[0]] = r[1] or ""
    pending_slots = {
        r["slot_name"] if db_type == "mysql" else r[0] for r in pending_rows
    }

    for s in ["C1", "C2", "C3"]:
      if not occupied.get(s) and s not in pending_slots:
        return s
    return None

  def find_slot_by_rfid(self, rfid_uid):
    """Tìm vị trí mà thẻ RFID này đang đỗ."""
    if not rfid_uid:
      return None
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      param_mark = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          "SELECT slot_name FROM slot_status WHERE current_rfid ="
          f" {param_mark}",
          (rfid_uid,),
      )
      row = cursor.fetchone()
      conn.close()

    if not row:
      return None
    return row["slot_name"] if db_type == "mysql" else row[0]

  def find_slot_by_plate(self, plate_number):
    """Tìm vị trí đang giữ xe theo biển số, không phụ thuộc cảm biến IR."""
    if not plate_number:
      return None
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          f"SELECT slot_name FROM slot_status WHERE current_plate = {p} "
          f"AND current_rfid <> {p}",
          (plate_number, ""),
      )
      row = cursor.fetchone()
      conn.close()
    if not row:
      return None
    return row["slot_name"] if db_type == "mysql" else row[0]

  def rfid_entry(self, slot, plate_number, rfid_uid, image_path=""):
    """Lưu thông tin xe VÀO bãi đỗ."""
    now_full = now_full_str()
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"

      # Ghi logs
      cursor.execute(
          f"""INSERT INTO logs (timestamp, slot_name, plate_number, rfid_uid, image_path)
             VALUES ({p}, {p}, {p}, {p}, {p})""",
          (now_full, slot, plate_number, rfid_uid, image_path),
      )

      # Cập nhật slot_status
      cursor.execute(
          f"""UPDATE slot_status SET status = 'F', time_in = {p}, current_plate = {p},
             current_rfid = {p}, image_path = {p} WHERE slot_name = {p}""",
          (now_full, plate_number, rfid_uid, image_path, slot),
      )

      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def request_entry_pending(self, slot, plate_number, rfid_uid, image_path=""):
    """Lưu xe vào danh sách chờ xác nhận, chưa ghi vào lịch sử chính."""
    now_full = now_full_str()
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          f"""DELETE FROM pending_entry WHERE slot_name = {p}""", (slot,)
      )
      cursor.execute(
          f"""INSERT INTO pending_entry
             (slot_name, plate_number, rfid_uid, requested_at, image_path)
             VALUES ({p}, {p}, {p}, {p}, {p})""",
          (slot, plate_number, rfid_uid, now_full, image_path),
      )
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def get_pending_entries(self):
    """Lấy xe vào đang chờ xác nhận."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute(
          "SELECT slot_name, plate_number, rfid_uid, requested_at, image_path "
          "FROM pending_entry ORDER BY requested_at DESC"
      )
      rows = cursor.fetchall()
      conn.close()

    if db_type == "mysql":
      return [dict(r) for r in rows]
    return [
        {
            "slot_name": r[0],
            "plate_number": r[1],
            "rfid_uid": r[2],
            "requested_at": r[3],
            "image_path": r[4] or "",
        }
        for r in rows
    ]

  def confirm_entry_pending(self, slot):
    """Xác nhận xe vào và chỉ lúc này mới ghi vào logs/slot_status."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          f"SELECT plate_number, rfid_uid, image_path FROM pending_entry "
          f"WHERE slot_name = {p}",
          (slot,),
      )
      row = cursor.fetchone()
      if not row:
        conn.close()
        return None
      if db_type == "mysql":
        plate, rfid, image_path = (
            row["plate_number"], row["rfid_uid"], row["image_path"] or ""
        )
      else:
        plate, rfid, image_path = row[0], row[1], row[2] or ""
      cursor.execute(f"DELETE FROM pending_entry WHERE slot_name = {p}", (slot,))
      if db_type == "sqlite":
        conn.commit()
      conn.close()

    self.rfid_entry(slot, plate, rfid, image_path)
    return {"slot": slot, "plate": plate, "rfid": rfid}

  def cancel_entry_pending(self, slot):
    """Hủy xe vào đang chờ xác nhận."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(f"DELETE FROM pending_entry WHERE slot_name = {p}", (slot,))
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def request_exit_pending(self, slot, image_path=""):
    """Quẹt thẻ lần 2 -> Đưa vào danh sách chờ xác nhận (Pending Exit)."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"

      cursor.execute(
          f"""SELECT time_in, current_plate, current_rfid FROM slot_status WHERE slot_name = {p}""",
          (slot,),
      )
      row = cursor.fetchone()
      if not row:
        conn.close()
        return False

      if db_type == "mysql":
        time_in = row["time_in"] or ""
        plate = row["current_plate"] or ""
        rfid = row["current_rfid"] or ""
      else:
        time_in = row[0] or ""
        plate = row[1] or ""
        rfid = row[2] or ""

      if not rfid:
        conn.close()
        return False

      fee = calc_fee(time_in, now_full_str())
      now_full = now_full_str()

      # Xóa pending cũ nếu có và thêm mới
      cursor.execute(
          f"DELETE FROM pending_exit WHERE slot_name = {p}", (slot,)
      )
      cursor.execute(
          f"""INSERT INTO pending_exit (slot_name, plate_number, rfid_uid, time_in, requested_at, fee_estimate, image_path)
             VALUES ({p}, {p}, {p}, {p}, {p}, {p}, {p})""",
          (slot, plate, rfid, time_in, now_full, fee, image_path),
      )

      if db_type == "sqlite":
        conn.commit()
      conn.close()
      return True

  def get_pending_exits(self):
    """Lấy danh sách các xe đang chờ bảo vệ bấm xác nhận ra."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("""
                SELECT slot_name, plate_number, rfid_uid, time_in, requested_at, fee_estimate, image_path 
                FROM pending_exit ORDER BY requested_at DESC
            """)
      rows = cursor.fetchall()
      conn.close()

    result = []
    if db_type == "mysql":
      for r in rows:
        result.append({
            "slot_name": r["slot_name"],
            "plate_number": r["plate_number"],
            "rfid_uid": r["rfid_uid"],
            "time_in": r["time_in"],
            "requested_at": r["requested_at"],
            "fee_estimate": r["fee_estimate"] or 1000,
            "image_path": r["image_path"] or "",
        })
    else:
      for r in rows:
        result.append({
            "slot_name": r[0],
            "plate_number": r[1],
            "rfid_uid": r[2],
            "time_in": r[3],
            "requested_at": r[4],
            "fee_estimate": r[5] or 1000,
            "image_path": r[6] or "",
        })
    return result

  def confirm_exit_pending(self, slot):
    """Bảo vệ bấm 'Xác nhận xe ra': Ghi exit_logs, cộng doanh thu, giải phóng vị trí đỗ."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"

      cursor.execute(
          f"SELECT slot_name FROM pending_exit WHERE slot_name = {p}",
          (slot,),
      )
      if not cursor.fetchone():
        conn.close()
        return None

      cursor.execute(
          f"SELECT time_in, current_plate, current_rfid FROM slot_status WHERE"
          f" slot_name = {p}",
          (slot,),
      )
      row = cursor.fetchone()
      if not row:
        conn.close()
        return None

      if db_type == "mysql":
        time_in = row["time_in"] or ""
        plate = row["current_plate"] or ""
        rfid = row["current_rfid"] or ""
      else:
        time_in = row[0] or ""
        plate = row[1] or ""
        rfid = row[2] or ""

      now_full = now_full_str()
      fee = calc_fee(time_in, now_full)

      # Xóa khỏi pending_exit
      cursor.execute(
          f"DELETE FROM pending_exit WHERE slot_name = {p}", (slot,)
      )

      # Cập nhật slot_status (giải phóng thẻ & biển số)
      cursor.execute(
          f"""UPDATE slot_status SET status = 'E', time_out = {p}, last_fee = {p},
             current_plate = '', current_rfid = '', image_path = '' WHERE slot_name = {p}""",
          (now_full, fee, slot),
      )

      # Ghi vào exit_logs
      cursor.execute(
          f"""INSERT INTO exit_logs (slot_name, plate_number, rfid_uid, time_in, time_out, fee)
             VALUES ({p}, {p}, {p}, {p}, {p}, {p})""",
          (slot, plate or "KHONG_XAC_DINH", rfid, time_in, now_full, fee),
      )

      # Cộng vào tổng doanh thu
      cursor.execute(
          f"UPDATE revenue SET total = total + {p} WHERE id = 1", (fee,)
      )

      if db_type == "sqlite":
        conn.commit()
      conn.close()
      return {
          "slot": slot,
          "plate": plate,
          "rfid": rfid,
          "time_in": time_in,
          "time_out": now_full,
          "fee": fee,
      }

  def cancel_exit_pending(self, slot):
    """Hủy yêu cầu xe ra."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(
          f"DELETE FROM pending_exit WHERE slot_name = {p}", (slot,)
      )
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def get_slots_status(self):
    """Lấy dữ liệu 3 vị trí đỗ & tổng doanh thu."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute(
          "SELECT slot_name, status, time_in, time_out, last_fee,"
          " current_plate, current_rfid, image_path FROM slot_status"
      )
      rows = cursor.fetchall()

      cursor.execute("SELECT total FROM revenue WHERE id = 1")
      rev_row = cursor.fetchone()
      total_rev = 0
      if rev_row:
        total_rev = (
            rev_row["total"] if db_type == "mysql" else (rev_row[0] or 0)
        )
      conn.close()

    slots = {}
    if db_type == "mysql":
      for r in rows:
        slots[r["slot_name"]] = {
            "status": r["status"],
            "time_in": r["time_in"],
            "time_out": r["time_out"],
            "last_fee": r["last_fee"] or 0,
            "current_plate": r["current_plate"] or "",
            "current_rfid": r["current_rfid"] or "",
            "image_path": r["image_path"] or "",
        }
    else:
      for r in rows:
        slots[r[0]] = {
            "status": r[1],
            "time_in": r[2],
            "time_out": r[3],
            "last_fee": r[4] or 0,
            "current_plate": r[5] or "",
            "current_rfid": r[6] or "",
            "image_path": r[7] if len(r) > 7 else "",
        }

    return {"total_revenue": total_rev, "slots": slots}

  def get_all_logs(self, date_filter=None):
    """Lấy danh sách lịch sử xe VÀO."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("""
                SELECT id, slot_name, timestamp, plate_number, rfid_uid, image_path 
                FROM logs ORDER BY id DESC LIMIT 100
            """)
      rows = cursor.fetchall()
      conn.close()

    result = []
    if db_type == "mysql":
      for r in rows:
        result.append(dict(r))
    else:
      for r in rows:
        result.append({
            "id": r[0],
            "slot_name": r[1],
            "timestamp": r[2],
            "plate_number": r[3],
            "rfid_uid": r[4],
            "image_path": r[5] or "",
        })
    if date_filter:
      result = [r for r in result if (r["timestamp"] or "").startswith(date_filter)]
    return result

  def get_all_exit_logs(self, date_filter=None):
    """Lấy danh sách lịch sử xe RA."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("""
                SELECT id, slot_name, plate_number, rfid_uid, time_in, time_out, fee, image_path 
                FROM exit_logs ORDER BY id DESC LIMIT 100
            """)
      rows = cursor.fetchall()
      conn.close()

    result = []
    if db_type == "mysql":
      for r in rows:
        result.append(dict(r))
    else:
      for r in rows:
        result.append({
            "id": r[0],
            "slot_name": r[1],
            "plate_number": r[2],
            "rfid_uid": r[3],
            "time_in": r[4],
            "time_out": r[5],
            "fee": r[6],
            "image_path": r[7] if len(r) > 7 else "",
        })
    if date_filter:
      result = [
          r for r in result
          if (r["time_in"] or "").startswith(date_filter)
      ]
    return result

  def get_daily_revenue(self, date_filter):
    """Tổng phí xe ra theo ngày vào/đang xem."""
    if not date_filter:
      return 0
    rows = self.get_all_exit_logs(date_filter)
    return sum((row.get("fee") or 0) for row in rows)

  def delete_log_by_id(self, log_id):
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(f"DELETE FROM logs WHERE id = {p}", (log_id,))
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def delete_exit_log_by_id(self, log_id):
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      p = "%s" if db_type == "mysql" else "?"
      cursor.execute(f"DELETE FROM exit_logs WHERE id = {p}", (log_id,))
      if db_type == "sqlite":
        conn.commit()
      conn.close()

  def clear_all_logs(self):
    """Xóa trắng database để test lại từ đầu."""
    with _db_lock:
      conn, db_type = self.get_connection()
      cursor = conn.cursor()
      cursor.execute("DELETE FROM logs")
      cursor.execute("DELETE FROM exit_logs")
      cursor.execute("DELETE FROM pending_exit")
      cursor.execute("DELETE FROM pending_entry")
      cursor.execute("UPDATE revenue SET total = 0 WHERE id = 1")
      cursor.execute("""
                UPDATE slot_status SET status = 'E', time_in = '', time_out = '',
                last_fee = 0, current_plate = '', current_rfid = '', image_path = ''
            """)
      if db_type == "sqlite":
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='logs'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='exit_logs'")
        conn.commit()
      else:
        cursor.execute("ALTER TABLE logs AUTO_INCREMENT = 1")
        cursor.execute("ALTER TABLE exit_logs AUTO_INCREMENT = 1")
      conn.close()


# Singleton database instance
db = DatabaseManager()
db.init_db()
