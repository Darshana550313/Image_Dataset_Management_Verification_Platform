import mysql.connector
from mysql.connector import Error
import os
from werkzeug.security import generate_password_hash

def create_database():
    """Create the database and tables"""
    try:
        # Connect to MySQL server (without database)
        connection = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            port=3306
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Create database
            cursor.execute("CREATE DATABASE IF NOT EXISTS plant_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print("✅ Database 'plant_system' created or already exists")

            # Use the database
            cursor.execute("USE plant_system")

            # Create plants table
            cursor.execute("""
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
                )
            """)
            print("✅ Table 'plants' created")

            # Add user_id to older installations if the plants table already existed
            cursor.execute("""
                SELECT COUNT(*) AS column_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'plant_system' AND TABLE_NAME = 'plants' AND COLUMN_NAME = 'user_id'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE plants ADD COLUMN user_id INT NULL AFTER id")
                print("✅ Column 'plants.user_id' added")

            for column_name, after_column in [('marathi_name', 'name'), ('hindi_name', 'marathi_name')]:
                cursor.execute(f"""
                    SELECT COUNT(*) AS column_exists
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = 'plant_system' AND TABLE_NAME = 'plants' AND COLUMN_NAME = '{column_name}'
                """)
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f"ALTER TABLE plants ADD COLUMN {column_name} VARCHAR(255) NULL AFTER {after_column}")
                    print(f"✅ Column 'plants.{column_name}' added")

            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    email_verified TINYINT(1) DEFAULT 0,
                    verification_otp VARCHAR(10),
                    otp_expires_at DATETIME,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Table 'users' created")

            for column_name, definition in [
                ('email_verified', "TINYINT(1) DEFAULT 0"),
                ('verification_otp', "VARCHAR(10) NULL"),
                ('otp_expires_at', "DATETIME NULL")
            ]:
                cursor.execute(f"""
                    SELECT COUNT(*) AS column_exists
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = 'plant_system' AND TABLE_NAME = 'users' AND COLUMN_NAME = '{column_name}'
                """)
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {definition}")
                    print(f"✅ Column 'users.{column_name}' added")

            # Create plant_images table
            cursor.execute("""
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
                )
            """)
            print("✅ Table 'plant_images' created")

            cursor.execute("""
                SELECT COUNT(*) AS column_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = 'plant_system' AND TABLE_NAME = 'plant_images' AND COLUMN_NAME = 'root_image'
            """)
            if cursor.fetchone()[0] == 0:
                cursor.execute("ALTER TABLE plant_images ADD COLUMN root_image VARCHAR(500) NULL AFTER bark_image")
                print("✅ Column 'plant_images.root_image' added")

            # Create plant varieties and variety images tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plant_varieties (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    plant_id INT NOT NULL,
                    variety_name VARCHAR(255) NOT NULL,
                    marathi_name VARCHAR(255),
                    hindi_name VARCHAR(255),
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
                )
            """)
            print("✅ Table 'plant_varieties' created")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plant_variety_images (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    variety_id INT NOT NULL,
                    image_type VARCHAR(50) NOT NULL,
                    filename VARCHAR(500) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (variety_id) REFERENCES plant_varieties(id) ON DELETE CASCADE
                )
            """)
            print("✅ Table 'plant_variety_images' created")

            # Create admin_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    plant_id INT NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    admin_username VARCHAR(255) NOT NULL,
                    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE
                )
            """)
            print("✅ Table 'admin_logs' created")

            # Create admin_users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ Table 'admin_users' created")

            # Insert default admin user
            hashed_password = generate_password_hash('admin123')
            cursor.execute("""
                INSERT IGNORE INTO admin_users (username, password) 
                VALUES (%s, %s)
            """, ('admin', hashed_password))
            print("✅ Default admin user created (admin / admin123)")

            connection.commit()
            print("\n🌿 Database initialization complete!")
            print("   You can now run: python app.py")

    except Error as e:
        print(f"❌ Error: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("   MySQL connection closed")

if __name__ == '__main__':
    create_database()
