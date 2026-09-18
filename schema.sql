-- Script tạo cơ sở dữ liệu và bảng cho Hệ Thống Quản Lý Bãi Giữ Xe Thông Minh
-- Tương thích: MySQL 5.7 / MySQL 8.0 / MariaDB (XAMPP)

CREATE DATABASE IF NOT EXISTS `parking_system` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `parking_system`;

-- 1. Bảng lưu lịch sử lượt xe VÀO
CREATE TABLE IF NOT EXISTS `logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `timestamp` VARCHAR(50) NOT NULL COMMENT 'Thời gian vào dd/mm/yyyy HH:MM:SS',
    `slot_name` VARCHAR(20) DEFAULT 'C1' COMMENT 'Vị trí đỗ C1/C2/C3',
    `plate_number` VARCHAR(50) DEFAULT 'KHONG_XAC_DINH' COMMENT 'Biển số xe',
    `rfid_uid` VARCHAR(50) DEFAULT '' COMMENT 'Mã UID thẻ RFID',
    `image_path` VARCHAR(255) DEFAULT '' COMMENT 'Đường dẫn ảnh chụp lúc vào',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. Bảng lưu lịch sử lượt xe RA
CREATE TABLE IF NOT EXISTS `exit_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `slot_name` VARCHAR(20) DEFAULT 'C1',
    `plate_number` VARCHAR(50) DEFAULT 'KHONG_XAC_DINH',
    `rfid_uid` VARCHAR(50) DEFAULT '',
    `time_in` VARCHAR(50) NOT NULL,
    `time_out` VARCHAR(50) NOT NULL,
    `fee` INT DEFAULT 0 COMMENT 'Phí gửi xe (VND)',
    `image_path` VARCHAR(255) DEFAULT '' COMMENT 'Đường dẫn ảnh chụp lúc ra',
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 3. Bảng trạng thái hiện tại của từng vị trí đỗ (C1, C2, C3)
CREATE TABLE IF NOT EXISTS `slot_status` (
    `slot_name` VARCHAR(10) PRIMARY KEY,
    `status` VARCHAR(5) DEFAULT 'E' COMMENT 'E = Trống (Xanh), F = Có xe (Đỏ)',
    `time_in` VARCHAR(50) DEFAULT '',
    `time_out` VARCHAR(50) DEFAULT '',
    `last_fee` INT DEFAULT 0,
    `current_plate` VARCHAR(50) DEFAULT '',
    `current_rfid` VARCHAR(50) DEFAULT '',
    `image_path` VARCHAR(255) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 4. Bảng lưu tổng doanh thu
CREATE TABLE IF NOT EXISTS `revenue` (
    `id` INT PRIMARY KEY,
    `total` BIGINT DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 5. Bảng danh sách chờ xác nhận xe ra (quẹt lần 2 tạo pending, bấm xác nhận mới ra)
CREATE TABLE IF NOT EXISTS `pending_exit` (
    `slot_name` VARCHAR(10) PRIMARY KEY,
    `plate_number` VARCHAR(50) DEFAULT '',
    `rfid_uid` VARCHAR(50) DEFAULT '',
    `time_in` VARCHAR(50) DEFAULT '',
    `requested_at` VARCHAR(50) DEFAULT '',
    `fee_estimate` INT DEFAULT 0,
    `image_path` VARCHAR(255) DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Khởi tạo dữ liệu ban đầu cho 3 vị trí đỗ và doanh thu
INSERT IGNORE INTO `slot_status` (`slot_name`, `status`, `time_in`, `time_out`, `last_fee`, `current_plate`, `current_rfid`, `image_path`) 
VALUES 
('C1', 'E', '', '', 0, '', '', ''),
('C2', 'E', '', '', 0, '', '', ''),
('C3', 'E', '', '', 0, '', '', '');

INSERT IGNORE INTO `revenue` (`id`, `total`) VALUES (1, 0);

-- Một báo cáo duy nhất theo ngày, gồm cả ngày trống giữa ngày đầu và ngày cuối.
DROP VIEW IF EXISTS `logs_daily_report`;
DROP VIEW IF EXISTS `exit_logs_daily_report`;
CREATE OR REPLACE VIEW `daily_report` AS
WITH RECURSIVE
events AS (
    SELECT STR_TO_DATE(`timestamp`, '%d/%m/%Y %H:%i:%s') AS `event_date`, 0 AS `fee`
    FROM `logs`
    UNION ALL
    SELECT STR_TO_DATE(`time_in`, '%d/%m/%Y %H:%i:%s'), `fee`
    FROM `exit_logs`
),
bounds AS (
    SELECT MIN(DATE(`event_date`)) AS `first_day`,
           MAX(DATE(`event_date`)) AS `last_day`
    FROM events
),
calendar AS (
    SELECT `first_day` AS `day` FROM bounds WHERE `first_day` IS NOT NULL
    UNION ALL
    SELECT DATE_ADD(`day`, INTERVAL 1 DAY)
    FROM calendar JOIN bounds ON 1 = 1
    WHERE `day` < `last_day`
),
totals AS (
    SELECT DATE(`event_date`) AS `day`, COUNT(*) AS `event_count`,
           COALESCE(SUM(`fee`), 0) AS `total_fee`
    FROM events
    GROUP BY DATE(`event_date`)
)
SELECT DATE_FORMAT(calendar.`day`, '%d/%m/%Y') AS `ngay`,
       CASE WHEN COALESCE(totals.`event_count`, 0) = 0
            THEN 'KHONG CO DU LIEU' ELSE 'TONG' END AS `thong_bao`,
       COALESCE(totals.`event_count`, 0) AS `tong_luot_ra_vao`,
       COALESCE(totals.`total_fee`, 0) AS `tong_doanh_thu`
FROM calendar
LEFT JOIN totals ON totals.`day` = calendar.`day`;
