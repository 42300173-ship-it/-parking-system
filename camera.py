import os
import threading
import time
from datetime import datetime
import cv2
import numpy as np
import config


class CameraStream:

  def __init__(self, camera_index=config.CAMERA_INDEX):
    self.camera_index = camera_index
    self.cap = None
    self.running = False
    self.lock = threading.Lock()
    self.current_frame = None
    self.last_frame_time = 0
    self.thread = None
    self._is_dummy = False
    self.start()

  def _open_camera(self):
    try:
      # DirectShow backend on Windows for faster startup and reliability
      cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
      if not cap.isOpened():
        # Fallback to default backend
        cap = cv2.VideoCapture(self.camera_index)
      if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        print(
            f"[CAMERA] Ket noi thanh cong toi Camera index {self.camera_index}"
        )
        self._is_dummy = False
        return cap
    except Exception as e:
      print(f"[CAMERA ERROR] Loi khi mo camera ({e})")

    print("[CAMERA WARNING] Khong mo duoc webcam vat ly, bat che do gia lap.")
    self._is_dummy = True
    return None

  def _generate_dummy_frame(self):
    """Tạo khung hình giả lập khi không có webcam cắm vào."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    # Gradient background
    for y in range(480):
      img[y, :] = [int(30 + y * 0.1), int(20 + y * 0.05), 40]

    # Target box
    cv2.rectangle(img, (120, 140), (520, 340), (0, 255, 100), 2)
    cv2.putText(
        img,
        "DEMO MODE - CAMERA CHUA KET NOI",
        (140, 110),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 200, 255),
        2,
    )
    cv2.putText(
        img,
        "DAT BIEN SO VAO KHUNG NAY",
        (170, 240),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        2,
    )

    # Simulated plate
    cv2.rectangle(img, (220, 260), (420, 320), (255, 255, 255), -1)
    cv2.putText(
        img,
        "51A-123.45",
        (240, 305),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
    )

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    cv2.putText(
        img,
        f"LIVE: {now_str}",
        (15, 460),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 255, 0),
        1,
    )
    return img

  def start(self):
    if self.running:
      return
    self.running = True
    self.cap = self._open_camera()
    self.thread = threading.Thread(target=self._capture_loop, daemon=True)
    self.thread.start()

  def _capture_loop(self):
    while self.running:
      if self.cap and self.cap.isOpened():
        ret, frame = self.cap.read()
        if ret and frame is not None:
          with self.lock:
            self.current_frame = frame.copy()
            self.last_frame_time = time.time()
        else:
          time.sleep(0.02)
      else:
        # Dummy frame
        frame = self._generate_dummy_frame()
        with self.lock:
          self.current_frame = frame
          self.last_frame_time = time.time()
        time.sleep(0.04)

  def get_latest_frame(self):
    """Lấy frame ảnh mới nhất dạng numpy array (BGR)."""
    with self.lock:
      if self.current_frame is not None:
        return self.current_frame.copy()
    return self._generate_dummy_frame()

  def capture_snapshot(self, prefix="entry"):
    """Lấy ngay lập tức 1 khung hình sắc nét và lưu thành file trong captures/."""
    frame = self.get_latest_frame()
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    filename = f"{prefix}_{timestamp_str}.jpg"
    filepath = os.path.join(config.CAPTURES_DIR, filename)

    try:
      cv2.imwrite(filepath, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
      rel_path = f"captures/{filename}"
      return rel_path, frame
    except Exception as e:
      print(f"[CAPTURE ERROR] Loi luu anh ({e})")
      return "", frame

  def generate_mjpeg_stream(self):
    """Generator stream MJPEG cho trình duyệt web (cực mượt, không trễ)."""
    while self.running:
      frame = self.get_latest_frame()

      # Vẽ khung ngắm hỗ trợ căn biển số trên luồng live
      display_frame = frame.copy()
      h, w = display_frame.shape[:2]
      x_start, x_end = int(w * 0.18), int(w * 0.82)
      y_start, y_end = int(h * 0.22), int(h * 0.78)

      # 4 góc ngắm hiện đại (corner brackets)
      c_len = 30
      color = (0, 230, 118)  # Xanh ngọc neon
      thickness = 2
      # Top-left
      cv2.line(
          display_frame, (x_start, y_start), (x_start + c_len, y_start), color, thickness
      )
      cv2.line(
          display_frame, (x_start, y_start), (x_start, y_start + c_len), color, thickness
      )
      # Top-right
      cv2.line(
          display_frame, (x_end, y_start), (x_end - c_len, y_start), color, thickness
      )
      cv2.line(
          display_frame, (x_end, y_start), (x_end, y_start + c_len), color, thickness
      )
      # Bottom-left
      cv2.line(
          display_frame, (x_start, y_end), (x_start + c_len, y_end), color, thickness
      )
      cv2.line(
          display_frame, (x_start, y_end), (x_start, y_end - c_len), color, thickness
      )
      # Bottom-right
      cv2.line(
          display_frame, (x_end, y_end), (x_end - c_len, y_end), color, thickness
      )
      cv2.line(
          display_frame, (x_end, y_end), (x_end, y_end - c_len), color, thickness
      )

      # Nhãn ngắm
      cv2.putText(
          display_frame,
          "KHUNG QUET BIEN SO",
          (x_start + 5, y_start - 8),
          cv2.FONT_HERSHEY_SIMPLEX,
          0.5,
          color,
          1,
      )

      # Encode JPEG
      ret, jpeg = cv2.imencode(
          ".jpg", display_frame, [cv2.IMWRITE_JPEG_QUALITY, 75]
      )
      if not ret:
        time.sleep(0.03)
        continue

      frame_bytes = jpeg.tobytes()
      yield (
          b"--frame\r\n"
          b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
      )
      time.sleep(0.033)  # ~30 FPS

  def stop(self):
    self.running = False
    if self.cap and self.cap.isOpened():
      self.cap.release()


# Singleton camera instance
camera = CameraStream()
