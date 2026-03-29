-- ============================================================
--  LAUNDRY PRO - Complete Database Schema (v3 - CASCADE FKs)
-- ============================================================

CREATE DATABASE IF NOT EXISTS laundry_db;
USE laundry_db;

-- Drop tables in reverse FK order for clean re-run
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- ─── USERS ───────────────────────────────────────────────────
CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    username    VARCHAR(50)  UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,
    full_name   VARCHAR(100),
    email       VARCHAR(100),
    phone       VARCHAR(15),
    address     TEXT,
    role        ENUM('admin','user') DEFAULT 'user',
    status      ENUM('enabled','disabled') DEFAULT 'enabled',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── SETTINGS ────────────────────────────────────────────────
CREATE TABLE settings (
    id            INT PRIMARY KEY,
    shop_name     VARCHAR(100) DEFAULT 'Laundry Pro',
    working_days  VARCHAR(255),
    opening_time  TIME,
    closing_time  TIME,
    upi_id        VARCHAR(100) DEFAULT 'shop@upi',
    currency      VARCHAR(10)  DEFAULT 'Rs'
);

-- ─── SERVICE PRICING ─────────────────────────────────────────
CREATE TABLE services (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    unit        VARCHAR(30)  DEFAULT 'per kg',
    description TEXT,
    is_active   TINYINT(1)   DEFAULT 1
);

-- ─── ORDERS ──────────────────────────────────────────────────
CREATE TABLE orders (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT,
    service_id      INT,
    service_type    VARCHAR(100),
    cloth_type      VARCHAR(100),
    weight_kg       DECIMAL(5,2) DEFAULT 1.00,
    amount          DECIMAL(10,2),
    status          ENUM('Pending','Accepted','Processing','Ready','Delivered','Cancelled') DEFAULT 'Pending',
    payment_method  ENUM('UPI','Cash','Card') DEFAULT 'Cash',
    payment_status  ENUM('Pending','Paid') DEFAULT 'Pending',
    notes           TEXT,
    order_date      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    pickup_date     DATE,
    delivery_date   DATE,
    FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE SET NULL
);

-- ─── EXPENSES ────────────────────────────────────────────────
CREATE TABLE expenses (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    type        ENUM('credit','debit') NOT NULL,
    category    VARCHAR(100),
    amount      DECIMAL(10,2) NOT NULL,
    description TEXT,
    entry_date  DATE NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ─── NOTIFICATIONS ───────────────────────────────────────────
CREATE TABLE notifications (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT,
    message     TEXT,
    is_read     TINYINT(1) DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
--  SEED DATA
-- ============================================================
INSERT INTO users (username,password,full_name,email,role)
VALUES ('admin','admin123','Administrator','admin@laundrypro.com','admin');

INSERT INTO users (username,password,full_name,email,phone,role)
VALUES ('john','user123','John Doe','john@example.com','9876543210','user');

INSERT INTO settings VALUES
(1,'Laundry Pro','Monday,Tuesday,Wednesday,Thursday,Friday,Saturday','08:00:00','20:00:00','shop@upi','Rs');

INSERT INTO services (name,price,unit,description) VALUES
('Wash & Fold',    40.00,'per kg',   'Everyday laundry washed, dried and neatly folded'),
('Dry Cleaning',  120.00,'per piece','Premium care for delicate fabrics'),
('Steam Iron',     15.00,'per piece','Crisp wrinkle-free pressing'),
('Wash & Iron',    60.00,'per kg',   'Full wash + professional ironing'),
('Blanket/Curtain',150.00,'per piece','Heavy item deep cleaning');

INSERT INTO orders (user_id,service_id,service_type,cloth_type,weight_kg,amount,status,payment_method,payment_status,order_date,pickup_date,delivery_date)
VALUES
(2,1,'Wash & Fold',  'Cottons',3.00,120.00,'Delivered','Cash','Paid',   NOW()-INTERVAL 10 DAY,NOW()-INTERVAL 9 DAY, NOW()-INTERVAL 7 DAY),
(2,2,'Dry Cleaning', 'Silk',   1.00,120.00,'Processing','UPI','Paid',   NOW()-INTERVAL 3 DAY, NOW()-INTERVAL 2 DAY, NOW()+INTERVAL 2 DAY),
(2,3,'Steam Iron',   'Shirts', 5.00, 75.00,'Accepted',  'Cash','Pending',NOW()-INTERVAL 1 DAY,NOW(),               NOW()+INTERVAL 1 DAY),
(2,4,'Wash & Iron',  'Mixed',  2.00,120.00,'Pending',   'Cash','Pending',NOW(),                NOW()+INTERVAL 1 DAY,NOW()+INTERVAL 3 DAY);

INSERT INTO expenses (type,category,amount,description,entry_date) VALUES
('credit','Order Payment',120.00,'Order #1 payment',   CURDATE()-INTERVAL 10 DAY),
('credit','Order Payment',120.00,'Order #2 UPI',        CURDATE()-INTERVAL 3 DAY),
('debit', 'Utilities',    800.00,'Electricity bill',    CURDATE()-INTERVAL 5 DAY),
('debit', 'Supplies',     350.00,'Detergent & supplies',CURDATE()-INTERVAL 2 DAY),
('credit','Order Payment', 75.00,'Order #3 partial',    CURDATE()-INTERVAL 1 DAY),
('debit', 'Maintenance',  200.00,'Machine service',     CURDATE());