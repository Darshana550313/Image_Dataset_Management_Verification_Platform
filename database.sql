-- Plant Information Management System Database Schema
-- MySQL Database

CREATE DATABASE IF NOT EXISTS plant_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE plant_system;

-- ============================================
-- TABLE: plants
-- Stores all plant information submitted by users
-- ============================================
CREATE TABLE IF NOT EXISTS plants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    name VARCHAR(255) NOT NULL,
    marathi_name VARCHAR(255),
    hindi_name VARCHAR(255),
    scientific_name VARCHAR(255),
    family VARCHAR(255),
    plant_type VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    medicinal_uses TEXT,
    nutritional_benefits TEXT,
    varieties TEXT,
    submitted_by VARCHAR(255),
    status ENUM('pending', 'published', 'rejected') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    published_at TIMESTAMP NULL
);

-- ============================================
-- TABLE: plant_images
-- Stores all images for a single plant (grouped)
-- One row per plant = all images together
-- ============================================
CREATE TABLE IF NOT EXISTS plant_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    main_image VARCHAR(500),
    leaf_image VARCHAR(500),
    fruit_image VARCHAR(500),
    flower_image VARCHAR(500),
    bark_image VARCHAR(500),
    root_image VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

-- ============================================
-- TABLE: admin_logs
-- Tracks admin actions (publish, reject, unpublish, delete)
-- ============================================
CREATE TABLE IF NOT EXISTS admin_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    action VARCHAR(50) NOT NULL,
    admin_username VARCHAR(255) NOT NULL,
    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

-- ============================================
-- TABLE: admin_users
-- Admin login credentials
-- ============================================
CREATE TABLE IF NOT EXISTS admin_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: users
-- Registered users with demo OTP verification
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email_verified TINYINT(1) DEFAULT 0,
    verification_otp VARCHAR(10),
    otp_expires_at DATETIME,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: plant_varieties
-- Stores sub-types/varieties such as Hapus, Kesar, Devgad
-- ============================================
CREATE TABLE IF NOT EXISTS plant_varieties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    variety_name VARCHAR(255) NOT NULL,
    marathi_name VARCHAR(255),
    hindi_name VARCHAR(255),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS plant_variety_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    variety_id INT NOT NULL,
    image_type VARCHAR(50) NOT NULL,
    filename VARCHAR(500) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (variety_id) REFERENCES plant_varieties(id) ON DELETE CASCADE
);

-- Insert default admin user (username: admin, password: admin123)
-- Password is hashed using werkzeug.security.generate_password_hash
INSERT INTO admin_users (username, password) VALUES 
('admin', 'pbkdf2:sha256:600000$example$hash_here_replace_with_actual_hash');
