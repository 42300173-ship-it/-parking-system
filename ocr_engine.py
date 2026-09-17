import re
import cv2
import easyocr
import numpy as np

# Regular expressions cho biển số Việt Nam
VALID_PLATE_PATTERN = re.compile(
    r"^\d{2}[A-Z]\d?-\d{3}\.\d{2,3}$" r"|^\d{2}[A-Z]\d?-\d{4,5}$"
)


class OCREngine:

  def __init__(self):
    print("[OCR] Dang khoi tao EasyOCR...")
    try:
      self.reader = easyocr.Reader(["en"], gpu=True)
      print("[OCR] Da bat tang toc GPU NVIDIA.")
    except Exception as e:
      print(f"[OCR] Khong dung duoc GPU ({e}), chuyen sang CPU.")
      self.reader = easyocr.Reader(["en"], gpu=False)

  def to_rgb(self, img_np):
    if img_np.ndim == 2:
      return cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
    if img_np.shape[2] == 4:
      return cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
    if img_np.shape[2] == 3:
      # OpenCV mac dinh la BGR -> chuyen RGB
      return cv2.cvtColor(img_np, cv2.COLOR_BGR2RGB)
    return img_np

  def resize_for_ocr(self, img, target_width=400):
    h, w = img.shape[:2]
    if w <= target_width:
      return img
    scale = target_width / float(w)
    return cv2.resize(img, (target_width, int(h * scale)))

  def clean_plate_text(self, text):
    """Chuẩn hóa ký tự nhận diện thành định dạng biển số xe Việt Nam."""
    text = re.sub(
        r"\b(POWERSTAR|POWER|STAR|VIE|VIEE|VIE1|EV)\b", "", text.upper()
    )
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

    # Dạng xe máy 2 dòng: 59A1-123.45 hoặc 59A1-1234
    match_bike = re.search(r"(\d{2})([A-Z])([0-9])(\d{4,5})", raw)
    if match_bike:
      prov, char, num, tail = match_bike.groups()
      if len(tail) == 5:
        return f"{prov}{char}{num}-{tail[:3]}.{tail[3:]}"
      return f"{prov}{char}{num}-{tail}"

    # Dạng thiếu số sê-ri
    match_bike_missing_num = re.search(r"^(\d{2})([A-Z])(\d{5})$", raw)
    if match_bike_missing_num:
      prov, char, tail = match_bike_missing_num.groups()
      return f"{prov}{char}1-{tail[:3]}.{tail[3:]}"

    # Dạng ô tô: 51A-123.45 hoặc 51G-1234
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

  def is_valid_plate_format(self, text):
    return bool(VALID_PLATE_PATTERN.match(text or ""))

  def detect_and_crop_plate(self, img_np):
    """Tìm đường viền hình chữ nhật và cắt biển số (ghép 2 hàng nếu là biển xe máy)."""
    if len(img_np.shape) == 3:
      gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
      gray = img_np

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

          # Biển vuông/2 dòng (xe máy) -> ghép ngang để EasyOCR đọc chuẩn
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

  def recognize_plate(self, img_bgr):
    """Quy trình trọn gói nhận diện biển số xe từ frame ảnh BGR."""
    try:
      img_rgb = self.to_rgb(img_bgr)
      h_img, w_img = img_rgb.shape[:2]

      # Vùng ngắm trọng tâm (giữa ảnh)
      x_start, x_end = int(w_img * 0.18), int(w_img * 0.82)
      y_start, y_end = int(h_img * 0.22), int(h_img * 0.78)
      aim_crop = img_rgb[y_start:y_end, x_start:x_end]

      # Cắt contour biển số
      cropped_plate, found, bbox = self.detect_and_crop_plate(img_rgb)

      # OCR lượt 1
      primary_crop = cropped_plate if found else aim_crop
      small_primary = self.resize_for_ocr(primary_crop)
      results = self.reader.readtext(small_primary)
      primary_text = "".join([res[1] + " " for res in results])
      cleaned_text = self.clean_plate_text(primary_text)

      # Nếu chưa đúng định dạng chuẩn, thử OCR lượt 2 trên vùng ngắm trọng tâm
      if not self.is_valid_plate_format(cleaned_text):
        fallback_crop = aim_crop if found else cropped_plate
        small_fallback = self.resize_for_ocr(fallback_crop)
        results_fb = self.reader.readtext(small_fallback)
        fb_text = "".join([res[1] + " " for res in results_fb])
        cleaned_fb = self.clean_plate_text(fb_text)
        if self.is_valid_plate_format(cleaned_fb):
          cleaned_text = cleaned_fb
        elif len(cleaned_fb) > len(cleaned_text):
          cleaned_text = cleaned_fb

      if not cleaned_text:
        cleaned_text = "KHONG_XAC_DINH"

      is_valid = self.is_valid_plate_format(cleaned_text)
      return cleaned_text, is_valid

    except Exception as e:
      print(f"[OCR ERROR] Loi khi nhan dien bien so: {e}")
      return "KHONG_XAC_DINH", False


# Singleton OCR instance
ocr = OCREngine()
