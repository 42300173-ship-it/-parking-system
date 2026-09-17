import cv2

# Dùng dấu gạch chéo xuôi '/' để tránh lỗi đường dẫn trên Windows
path = 'D:/Hinh/canhan/hinh2.jpg'

img = cv2.imread(path)

# Kiểm tra xem có đọc được ảnh không trước khi hiển thị
if img is None:
    print("Lỗi: Không tìm thấy ảnh! Hãy kiểm tra lại đường dẫn D:/Hinh/canhan/hinh2.jpg")
else:
    cv2.imshow('tailen', img)
    cv2.waitKey(0)  # Viết thường chữ 'k'
    cv2.destroyAllWindows()