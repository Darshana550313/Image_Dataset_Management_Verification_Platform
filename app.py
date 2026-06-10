from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error
import os
import uuid
import csv
import io
import zipfile
import re
import random
import smtplib
from email.message import EmailMessage

from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

# Upload folder setup
UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = app.config['ALLOWED_EXTENSIONS']

PLANT_TYPES = [
    'Tree', 'Herb', 'Shrub', 'Grass', 'Climber', 'Creeper', 'Vine', 'Aquatic Plant',
    'Succulent', 'Cactus', 'Fern', 'Palm', 'Bamboo', 'Bulb', 'Tuber', 'Root Crop',
    'Epiphyte', 'Moss', 'Algae', 'Crop Plant', 'Wild Plant'
]
FUNCTIONAL_CATEGORIES = [
    'Fruit', 'Medicinal', 'Flowering', 'Vegetable', 'Ornamental', 'Timber', 'Spice',
    'Cereal', 'Pulse', 'Oilseed', 'Fiber', 'Fodder', 'Beverage', 'Aromatic',
    'Dye', 'Poisonous', 'Aquatic', 'Indoor', 'Succulent', 'Religious', 'Edible',
    'Root Vegetable', 'Leafy Vegetable', 'Tuber', 'Wild Edible'
]
IMAGE_FIELDS = [
    ('main_image', 'main_image'),
    ('leaf_image', 'leaf_image'),
    ('fruit_image', 'fruit_image'),
    ('flower_image', 'flower_image'),
    ('bark_image', 'bark_image'),
    ('root_image', 'root_image'),
]
VARIETY_IMAGE_TYPES = ['tree', 'leaf', 'fruit', 'flower', 'bark', 'root']

_schema_checked = False

# ============================================
# DATABASE CONNECTION HELPER
# ============================================
def get_db_connection():
    """Create and return a database connection"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=Config.MYSQL_PORT,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def ensure_user_schema():
    """Create user auth tables/columns without disturbing existing data."""
    global _schema_checked
    if _schema_checked:
        return

    connection = get_db_connection()
    if not connection:
        return

    cursor = connection.cursor(dictionary=True)
    try:
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

        for column_name, definition in [
            ('email_verified', "TINYINT(1) DEFAULT 0"),
            ('verification_otp', "VARCHAR(10) NULL"),
            ('otp_expires_at', "DATETIME NULL")
        ]:
            cursor.execute("""
                SELECT COUNT(*) AS column_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users' AND COLUMN_NAME = %s
            """, (Config.MYSQL_DB, column_name))
            row = cursor.fetchone()
            if not row or row.get('column_exists') == 0:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {definition}")

        cursor.execute("""
            SELECT COUNT(*) AS column_exists
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'plants' AND COLUMN_NAME = 'user_id'
        """, (Config.MYSQL_DB,))
        row = cursor.fetchone()
        if not row or row.get('column_exists') == 0:
            cursor.execute("ALTER TABLE plants ADD COLUMN user_id INT NULL AFTER id")

        for column_name, after_column in [('marathi_name', 'name'), ('hindi_name', 'marathi_name')]:
            cursor.execute("""
                SELECT COUNT(*) AS column_exists
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'plants' AND COLUMN_NAME = %s
            """, (Config.MYSQL_DB, column_name))
            row = cursor.fetchone()
            if not row or row.get('column_exists') == 0:
                cursor.execute(f"ALTER TABLE plants ADD COLUMN {column_name} VARCHAR(255) NULL AFTER {after_column}")

        cursor.execute("""
            SELECT COUNT(*) AS column_exists
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'plants' AND COLUMN_NAME = 'rejection_reason'
        """, (Config.MYSQL_DB,))
        row = cursor.fetchone()
        if not row or row.get('column_exists') == 0:
            cursor.execute("ALTER TABLE plants ADD COLUMN rejection_reason TEXT NULL AFTER status")

        cursor.execute("""
            SELECT COUNT(*) AS column_exists
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'plant_images' AND COLUMN_NAME = 'root_image'
        """, (Config.MYSQL_DB,))
        row = cursor.fetchone()
        if not row or row.get('column_exists') == 0:
            cursor.execute("ALTER TABLE plant_images ADD COLUMN root_image VARCHAR(500) NULL AFTER bark_image")

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

        connection.commit()
        _schema_checked = True
    except Error as e:
        connection.rollback()
        print(f"Schema update error: {e}")
    finally:
        cursor.close()
        connection.close()

@app.before_request
def run_schema_updates():
    ensure_user_schema()

# ============================================
# FILE UPLOAD HELPERS
# ============================================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploaded_file(file):
    """Save uploaded file and return the filename"""
    if file and allowed_file(file.filename):
        file.stream.seek(0, os.SEEK_END)
        file_size = file.stream.tell()
        file.stream.seek(0)
        if file_size > Config.MAX_IMAGE_FILE_SIZE:
            raise ValueError('Each image must be 3MB or smaller.')
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(filepath)
        return unique_filename
    return None

def save_uploaded_files(files):
    filenames = []
    for file in files:
        saved = save_uploaded_file(file)
        if saved:
            filenames.append(saved)
    return filenames

def is_devanagari_text(value):
    return True

def generate_otp():
    return f"{random.randint(100000, 999999)}"

def send_verification_email(email, otp):
    if not Config.MAIL_SERVER or not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD:
        print(f"Demo OTP for {email}: {otp}")
        return False

    message = EmailMessage()
    message['Subject'] = 'PlantInfo Email Verification OTP'
    message['From'] = Config.MAIL_DEFAULT_SENDER
    message['To'] = email
    message.set_content(f"Your PlantInfo verification OTP is {otp}. It is valid for 10 minutes.")

    with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as smtp:
        if Config.MAIL_USE_TLS:
            smtp.starttls()
        smtp.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        smtp.send_message(message)
    return True

def create_and_send_otp(cursor, user_id, email):
    otp = generate_otp()
    expires_at = datetime.now() + timedelta(minutes=10)
    cursor.execute("""
        UPDATE users
        SET verification_otp = %s, otp_expires_at = %s, email_verified = 0
        WHERE id = %s
    """, (otp, expires_at, user_id))
    session['demo_otp'] = otp
    sent = send_verification_email(email, otp)
    return otp, sent

def get_plant_varieties(cursor, plant_id):
    cursor.execute("SELECT * FROM plant_varieties WHERE plant_id = %s ORDER BY id ASC", (plant_id,))
    varieties = cursor.fetchall()
    for variety in varieties:
        cursor.execute("SELECT image_type, filename FROM plant_variety_images WHERE variety_id = %s ORDER BY id ASC", (variety['id'],))
        grouped = {image_type: [] for image_type in VARIETY_IMAGE_TYPES}
        for image in cursor.fetchall():
            grouped.setdefault(image['image_type'], []).append(image['filename'])
        variety['images'] = grouped
    return varieties

def save_varieties_from_form(cursor, plant_id):
    variety_count = int(request.form.get('variety_count', '0') or 0)
    for index in range(variety_count):
        variety_name = request.form.get(f'variety_name_{index}', '').strip()
        marathi_name = request.form.get(f'variety_marathi_name_{index}', '').strip()
        hindi_name = request.form.get(f'variety_hindi_name_{index}', '').strip()
        description = request.form.get(f'variety_description_{index}', '').strip()
        has_images = any(request.files.getlist(f'variety_{image_type}_images_{index}') for image_type in VARIETY_IMAGE_TYPES)

        if not variety_name and not has_images:
            continue
        if not variety_name:
            raise ValueError('Variety name is required when variety images are uploaded.')
        cursor.execute("""
            INSERT INTO plant_varieties (plant_id, variety_name, marathi_name, hindi_name, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (plant_id, variety_name, marathi_name, hindi_name, description))
        variety_id = cursor.lastrowid

        for image_type in VARIETY_IMAGE_TYPES:
            for filename in save_uploaded_files(request.files.getlist(f'variety_{image_type}_images_{index}')):
                cursor.execute("""
                    INSERT INTO plant_variety_images (variety_id, image_type, filename)
                    VALUES (%s, %s, %s)
                """, (variety_id, image_type, filename))

def find_published_duplicate(cursor, plant):
    scientific_name = (plant.get('scientific_name') or '').strip()
    plant_name = (plant.get('name') or '').strip()
    cursor.execute("""
        SELECT id, name, varieties
        FROM plants
        WHERE status = 'published'
          AND id <> %s
          AND (
              LOWER(TRIM(name)) = LOWER(TRIM(%s))
              OR (
                  %s <> ''
                  AND (
                      LOWER(TRIM(%s)) LIKE CONCAT('%%', LOWER(TRIM(name)), '%%')
                      OR LOWER(TRIM(name)) LIKE CONCAT('%%', LOWER(TRIM(%s)), '%%')
                  )
              )
              OR (%s <> '' AND LOWER(TRIM(scientific_name)) = LOWER(TRIM(%s)))
          )
        ORDER BY published_at ASC, id ASC
        LIMIT 1
    """, (plant.get('id'), plant_name, plant_name, plant_name, plant_name, scientific_name, scientific_name))
    return cursor.fetchone()

def split_variety_names(varieties_text):
    return [name.strip() for name in re.split(r'[,;\n]+', varieties_text or '') if name.strip()]

def infer_variety_name_from_duplicate(source_plant, target_plant):
    source_name = (source_plant.get('name') or '').strip()
    target_name = (target_plant.get('name') or '').strip()
    if not source_name or not target_name or source_name.lower() == target_name.lower():
        return ''

    inferred = re.sub(re.escape(target_name), '', source_name, flags=re.IGNORECASE).strip()
    inferred = re.sub(r'^[\s,;/\-()]+|[\s,;/\-()]+$', '', inferred).strip()
    return inferred

def copy_base_images_to_variety(cursor, source_plant_id, variety_id):
    cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (source_plant_id,))
    images = cursor.fetchone()
    if not images:
        return

    image_map = {
        'main_image': 'tree',
        'leaf_image': 'leaf',
        'fruit_image': 'fruit',
        'flower_image': 'flower',
        'bark_image': 'bark',
        'root_image': 'root'
    }
    for column_name, image_type in image_map.items():
        filename = images.get(column_name)
        if filename:
            cursor.execute("""
                INSERT INTO plant_variety_images (variety_id, image_type, filename)
                VALUES (%s, %s, %s)
            """, (variety_id, image_type, filename))

def merge_submission_varieties(cursor, source_plant, target_plant):
    cursor.execute("SELECT LOWER(TRIM(variety_name)) AS variety_name FROM plant_varieties WHERE plant_id = %s", (target_plant['id'],))
    existing_names = {row['variety_name'] for row in cursor.fetchall() if row.get('variety_name')}

    cursor.execute("SELECT * FROM plant_varieties WHERE plant_id = %s ORDER BY id ASC", (source_plant['id'],))
    source_varieties = cursor.fetchall()
    added_names = []

    for variety in source_varieties:
        variety_name = (variety.get('variety_name') or '').strip()
        normalized_name = variety_name.lower()
        if not variety_name or normalized_name in existing_names:
            continue

        cursor.execute("""
            INSERT INTO plant_varieties (plant_id, variety_name, marathi_name, hindi_name, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            target_plant['id'],
            variety_name,
            variety.get('marathi_name'),
            variety.get('hindi_name'),
            variety.get('description')
        ))
        new_variety_id = cursor.lastrowid

        cursor.execute("SELECT image_type, filename FROM plant_variety_images WHERE variety_id = %s", (variety['id'],))
        for image in cursor.fetchall():
            cursor.execute("""
                INSERT INTO plant_variety_images (variety_id, image_type, filename)
                VALUES (%s, %s, %s)
            """, (new_variety_id, image['image_type'], image['filename']))

        existing_names.add(normalized_name)
        added_names.append(variety_name)

    inferred_variety = infer_variety_name_from_duplicate(source_plant, target_plant)
    if inferred_variety and inferred_variety.lower() not in existing_names:
        cursor.execute("""
            INSERT INTO plant_varieties (plant_id, variety_name, marathi_name, hindi_name, description)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            target_plant['id'],
            inferred_variety,
            source_plant.get('marathi_name'),
            source_plant.get('hindi_name'),
            source_plant.get('description')
        ))
        copy_base_images_to_variety(cursor, source_plant['id'], cursor.lastrowid)
        existing_names.add(inferred_variety.lower())
        added_names.append(inferred_variety)

    for variety_name in split_variety_names(source_plant.get('varieties')):
        normalized_name = variety_name.lower()
        if normalized_name in existing_names:
            continue
        cursor.execute("""
            INSERT INTO plant_varieties (plant_id, variety_name)
            VALUES (%s, %s)
        """, (target_plant['id'], variety_name))
        existing_names.add(normalized_name)
        added_names.append(variety_name)

    if added_names:
        current_names = split_variety_names(target_plant.get('varieties'))
        current_normalized = {name.lower() for name in current_names}
        for variety_name in added_names:
            if variety_name.lower() not in current_normalized:
                current_names.append(variety_name)
                current_normalized.add(variety_name.lower())
        cursor.execute("UPDATE plants SET varieties = %s WHERE id = %s", (', '.join(current_names), target_plant['id']))

    return added_names

def safe_dataset_folder_name(name):
    """Create a filesystem-safe folder name for dataset ZIP entries."""
    cleaned = re.sub(r'[^\w\s-]', '', name or 'Unknown Plant').strip()
    cleaned = re.sub(r'[-\s]+', '_', cleaned)
    return cleaned or 'Unknown_Plant'

def build_dataset_metadata_csv(plants):
    output = io.StringIO()
    fieldnames = [
        'id', 'name', 'marathi_name', 'hindi_name', 'scientific_name', 'family', 'plant_type', 'category',
        'description', 'medicinal_uses', 'nutritional_benefits', 'varieties',
        'submitted_by', 'status', 'created_at', 'updated_at', 'published_at',
        'main_image', 'leaf_image', 'fruit_image', 'flower_image', 'bark_image', 'root_image'
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for plant in plants:
        writer.writerow({field: plant.get(field, '') for field in fieldnames})
    return output.getvalue()

def get_dataset_plants(status_filter='published'):
    connection = get_db_connection()
    plants = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        where_clause = "WHERE p.status = 'published'" if status_filter == 'published' else ''
        cursor.execute(f"""
            SELECT p.*, pi.main_image, pi.leaf_image, pi.fruit_image, pi.flower_image, pi.bark_image, pi.root_image
            FROM plants p
            LEFT JOIN plant_images pi ON p.id = pi.plant_id
            {where_clause}
            ORDER BY p.created_at DESC
        """)
        plants = cursor.fetchall()
        cursor.close()
        connection.close()
    return plants

def write_plant_to_dataset_zip(dataset_zip, cursor, plant):
    plant_folder = safe_dataset_folder_name(plant.get('name'))
    for field_name, label in IMAGE_FIELDS:
        image_filename = plant.get(field_name)
        if not image_filename:
            continue
        image_path = os.path.join(UPLOAD_FOLDER, image_filename)
        if os.path.exists(image_path):
            dataset_zip.write(image_path, f"images/{plant_folder}/plant/{label}_{image_filename}")

    varieties = get_plant_varieties(cursor, plant.get('id'))
    for variety in varieties:
        variety_folder = safe_dataset_folder_name(variety.get('variety_name'))
        for image_type, files in variety.get('images', {}).items():
            for filename in files:
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(image_path):
                    dataset_zip.write(image_path, f"images/{plant_folder}/varieties/{variety_folder}/{image_type}/{filename}")

# ============================================
# ADMIN LOGIN REQUIRED DECORATOR
# ============================================
def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_loggedin' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to continue', 'warning')
            return redirect(url_for('user_login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

# ============================================
# USER ROUTES
# ============================================

@app.route('/')
def index():
    """Homepage - Show published plants with search, filters, and sorting"""
    search = request.args.get('search', '').strip()
    plant_type = request.args.get('plant_type', '').strip()
    category = request.args.get('category', '').strip()
    sort_by = request.args.get('sort_by', 'name_asc').strip()
    if sort_by not in ['name_asc', 'name_desc']:
        sort_by = 'name_asc'

    connection = get_db_connection()
    plants = []
    total_count = 0
    if connection:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) AS total FROM plants WHERE status = 'published'")
        total_count = cursor.fetchone()['total']

        query = """
            SELECT p.*, pi.main_image
            FROM plants p
            LEFT JOIN plant_images pi ON p.id = pi.plant_id
            WHERE p.status = 'published'
        """
        params = []

        if search:
            query += """
                AND (
                    p.name LIKE %s OR p.marathi_name LIKE %s OR p.hindi_name LIKE %s
                    OR p.scientific_name LIKE %s OR p.family LIKE %s
                    OR p.description LIKE %s OR p.medicinal_uses LIKE %s
                    OR p.nutritional_benefits LIKE %s
                )
            """
            search_term = f"%{search}%"
            params.extend([search_term] * 8)

        if plant_type in PLANT_TYPES:
            query += " AND p.plant_type = %s"
            params.append(plant_type)

        if category in FUNCTIONAL_CATEGORIES:
            query += " AND p.category = %s"
            params.append(category)

        sort_options = {
            'name_asc': 'p.name ASC',
            'name_desc': 'p.name DESC'
        }
        query += f" ORDER BY {sort_options.get(sort_by, sort_options['name_asc'])}"

        cursor.execute(query, params)
        plants = cursor.fetchall()
        cursor.close()
        connection.close()

    return render_template(
        'index.html',
        plants=plants,
        total_count=total_count,
        search=search,
        plant_type=plant_type if plant_type in PLANT_TYPES else '',
        category=category if category in FUNCTIONAL_CATEGORIES else '',
        sort_by=sort_by,
        filter_values={
            'plant_types': PLANT_TYPES,
            'categories': FUNCTIONAL_CATEGORIES
        }
    )

@app.route('/upload', methods=['GET', 'POST'])
@user_required
def upload():
    """User upload page - Submit new plant with images"""
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        marathi_name = request.form.get('marathi_name', '').strip()
        hindi_name = request.form.get('hindi_name', '').strip()
        scientific_name = request.form.get('scientific_name', '').strip()
        family = request.form.get('family', '').strip()
        plant_type = request.form.get('plant_type', '').strip()
        category = request.form.get('category', '').strip()
        description = request.form.get('description', '').strip()
        medicinal_uses = request.form.get('medicinal_uses', '').strip()
        nutritional_benefits = request.form.get('nutritional_benefits', '').strip()
        varieties = request.form.get('varieties', '').strip()
        submitted_by = session.get('user_name', '').strip()

        # Validation
        if not name:
            flash('Plant Name is required!', 'danger')
            return redirect(url_for('upload'))
        if not plant_type:
            flash('Plant Type is required!', 'danger')
            return redirect(url_for('upload'))
        if not category:
            flash('Category is required!', 'danger')
            return redirect(url_for('upload'))
        # Check main image (required)
        main_image_file = request.files.get('main_image')
        if not main_image_file or main_image_file.filename == '':
            flash('Main Tree Image is required!', 'danger')
            return redirect(url_for('upload'))

        try:
            # Save main image
            main_image = save_uploaded_file(main_image_file)
            if not main_image:
                flash('Invalid main image file!', 'danger')
                return redirect(url_for('upload'))

            # Save optional images
            leaf_image = save_uploaded_file(request.files.get('leaf_image'))
            fruit_image = save_uploaded_file(request.files.get('fruit_image'))
            flower_image = save_uploaded_file(request.files.get('flower_image'))
            bark_image = save_uploaded_file(request.files.get('bark_image'))
            root_image = save_uploaded_file(request.files.get('root_image'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('upload'))

        # Insert into database
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor()
            try:
                # Insert plant info
                cursor.execute("""
                    INSERT INTO plants 
                    (user_id, name, marathi_name, hindi_name, scientific_name, family, plant_type, category, description, 
                     medicinal_uses, nutritional_benefits, varieties, submitted_by, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """, (session.get('user_id'), name, marathi_name, hindi_name, scientific_name, family, plant_type, category, description,
                      medicinal_uses, nutritional_benefits, varieties, submitted_by))

                plant_id = cursor.lastrowid

                # Insert images (all grouped under one plant)
                cursor.execute("""
                    INSERT INTO plant_images 
                    (plant_id, main_image, leaf_image, fruit_image, flower_image, bark_image, root_image)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (plant_id, main_image, leaf_image, fruit_image, flower_image, bark_image, root_image))

                save_varieties_from_form(cursor, plant_id)

                connection.commit()
                flash('✅ Plant submitted successfully! Admin will review and publish it soon.', 'success')
                return redirect(url_for('my_submissions'))

            except ValueError as e:
                connection.rollback()
                flash(str(e), 'danger')
            except Error as e:
                connection.rollback()
                flash(f'Error saving plant: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection failed!', 'danger')

    return render_template('upload.html', plant_types=PLANT_TYPES, categories=FUNCTIONAL_CATEGORIES)

@app.route('/register', methods=['GET', 'POST'])
def user_register():
    """Create a user account for plant submissions."""
    if 'user_id' in session:
        return redirect(url_for('my_submissions'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash('Name, email, and password are required.', 'danger')
            return redirect(url_for('user_register'))
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('user_register'))
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return redirect(url_for('user_register'))

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('This email is already registered. Please login.', 'warning')
                    return redirect(url_for('user_login'))

                cursor.execute("""
                    INSERT INTO users (name, email, password, email_verified)
                    VALUES (%s, %s, %s, 0)
                """, (name, email, generate_password_hash(password)))
                user_id = cursor.lastrowid
                create_and_send_otp(cursor, user_id, email)
                connection.commit()
                session['pending_user_id'] = user_id
                session['pending_user_email'] = email
                flash('Account created. Please verify your email with OTP.', 'success')
                return redirect(url_for('verify_email'))
            except Error as e:
                connection.rollback()
                flash(f'Error creating account: {e}', 'danger')
            finally:
                cursor.close()
                connection.close()
        else:
            flash('Database connection failed!', 'danger')

    return render_template('auth/register.html')

@app.route('/verify-email', methods=['GET', 'POST'])
def verify_email():
    """Verify registered user email using OTP."""
    pending_user_id = session.get('pending_user_id')
    pending_email = session.get('pending_user_email')
    if not pending_user_id:
        flash('Please register or login first.', 'warning')
        return redirect(url_for('user_login'))

    if request.method == 'POST':
        otp = request.form.get('otp', '').strip()
        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute("SELECT * FROM users WHERE id = %s", (pending_user_id,))
                user = cursor.fetchone()
                if not user:
                    flash('User not found.', 'danger')
                    return redirect(url_for('user_register'))

                if user.get('verification_otp') == otp and user.get('otp_expires_at') and user['otp_expires_at'] >= datetime.now():
                    cursor.execute("""
                        UPDATE users
                        SET email_verified = 1, verification_otp = NULL, otp_expires_at = NULL
                        WHERE id = %s
                    """, (pending_user_id,))
                    connection.commit()
                    session.pop('pending_user_id', None)
                    session.pop('pending_user_email', None)
                    session.pop('demo_otp', None)
                    session['user_id'] = user['id']
                    session['user_name'] = user['name']
                    session['user_email'] = user['email']
                    flash('Email verified successfully!', 'success')
                    return redirect(url_for('my_submissions'))

                flash('Invalid or expired OTP.', 'danger')
            finally:
                cursor.close()
                connection.close()

    return render_template('auth/verify_email.html', email=pending_email, demo_otp=session.get('demo_otp'))

@app.route('/resend-otp', methods=['POST'])
def resend_otp():
    pending_user_id = session.get('pending_user_id')
    pending_email = session.get('pending_user_email')
    if not pending_user_id or not pending_email:
        return redirect(url_for('user_login'))

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            create_and_send_otp(cursor, pending_user_id, pending_email)
            connection.commit()
            flash('New OTP sent.', 'success')
        except Exception as e:
            connection.rollback()
            flash(f'Could not send OTP: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()
    return redirect(url_for('verify_email'))

@app.route('/login', methods=['GET', 'POST'])
def user_login():
    """User login page."""
    if 'user_id' in session:
        return redirect(url_for('my_submissions'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        next_url = request.args.get('next') or url_for('my_submissions')

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()
            cursor.close()
            connection.close()

            if user and check_password_hash(user['password'], password):
                if not user.get('email_verified'):
                    session['pending_user_id'] = user['id']
                    session['pending_user_email'] = user['email']
                    otp_connection = get_db_connection()
                    if otp_connection:
                        otp_cursor = otp_connection.cursor()
                        create_and_send_otp(otp_cursor, user['id'], user['email'])
                        otp_connection.commit()
                        otp_cursor.close()
                        otp_connection.close()
                    flash('Please verify your email before login.', 'warning')
                    return redirect(url_for('verify_email'))
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_email'] = user['email']
                flash('Logged in successfully!', 'success')
                return redirect(next_url)

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')

@app.route('/logout')
def user_logout():
    """User logout."""
    session.pop('user_id', None)
    session.pop('user_name', None)
    session.pop('user_email', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('index'))

@app.route('/my-submissions')
@user_required
def my_submissions():
    """Show plants submitted by the logged-in user."""
    connection = get_db_connection()
    plants = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT p.*, pi.main_image
            FROM plants p
            LEFT JOIN plant_images pi ON p.id = pi.plant_id
            WHERE p.user_id = %s
            ORDER BY p.created_at DESC
        """, (session.get('user_id'),))
        plants = cursor.fetchall()
        cursor.close()
        connection.close()
    return render_template('my_submissions.html', plants=plants)

@app.route('/my-submissions/edit/<int:plant_id>', methods=['GET', 'POST'])
@user_required
def user_edit_plant(plant_id):
    """Allow users to edit only pending or rejected submissions."""
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed!', 'danger')
        return redirect(url_for('my_submissions'))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM plants WHERE id = %s AND user_id = %s", (plant_id, session.get('user_id')))
        plant = cursor.fetchone()
        if not plant:
            flash('Plant not found or access denied.', 'danger')
            return redirect(url_for('my_submissions'))
        if plant.get('status') == 'published':
            flash('Published plant data cannot be edited. Please contact admin if changes are needed.', 'warning')
            return redirect(url_for('my_submissions'))

        cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (plant_id,))
        images = cursor.fetchone()
        varieties = get_plant_varieties(cursor, plant_id)

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            marathi_name = request.form.get('marathi_name', '').strip()
            hindi_name = request.form.get('hindi_name', '').strip()
            scientific_name = request.form.get('scientific_name', '').strip()
            family = request.form.get('family', '').strip()
            plant_type = request.form.get('plant_type', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            medicinal_uses = request.form.get('medicinal_uses', '').strip()
            nutritional_benefits = request.form.get('nutritional_benefits', '').strip()
            varieties_text = request.form.get('varieties', '').strip()

            if not name or not plant_type or not category:
                flash('Plant name, type, and category are required.', 'danger')
                return redirect(url_for('user_edit_plant', plant_id=plant_id))

            cursor.execute("""
                UPDATE plants
                SET name = %s, marathi_name = %s, hindi_name = %s, scientific_name = %s,
                    family = %s, plant_type = %s, category = %s, description = %s,
                    medicinal_uses = %s, nutritional_benefits = %s, varieties = %s,
                    status = 'pending', rejection_reason = NULL, published_at = NULL
                WHERE id = %s AND user_id = %s
            """, (
                name, marathi_name, hindi_name, scientific_name, family, plant_type, category,
                description, medicinal_uses, nutritional_benefits, varieties_text,
                plant_id, session.get('user_id')
            ))

            image_updates = {}
            for field_name, _ in IMAGE_FIELDS:
                uploaded = save_uploaded_file(request.files.get(field_name))
                if uploaded:
                    image_updates[field_name] = uploaded

            if image_updates:
                if images:
                    set_clause = ', '.join([f"{field} = %s" for field in image_updates])
                    cursor.execute(
                        f"UPDATE plant_images SET {set_clause} WHERE plant_id = %s",
                        list(image_updates.values()) + [plant_id]
                    )
                else:
                    cursor.execute("""
                        INSERT INTO plant_images (plant_id, main_image, leaf_image, fruit_image, flower_image, bark_image, root_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        plant_id,
                        image_updates.get('main_image'),
                        image_updates.get('leaf_image'),
                        image_updates.get('fruit_image'),
                        image_updates.get('flower_image'),
                        image_updates.get('bark_image'),
                        image_updates.get('root_image')
                    ))

            save_varieties_from_form(cursor, plant_id)
            cursor.execute("""
                INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                VALUES (%s, 'user_update', %s, %s)
            """, (
                plant_id,
                session.get('user_email', session.get('user_name', 'user')),
                'User updated this plant. Admin review and republish required.'
            ))
            connection.commit()
            flash('Plant updated successfully! It is now sent to admin for review and republish.', 'success')
            return redirect(url_for('my_submissions'))

        return render_template(
            'user_edit_plant.html',
            plant=plant,
            images=images,
            varieties=varieties,
            plant_types=PLANT_TYPES,
            categories=FUNCTIONAL_CATEGORIES
        )
    except ValueError as e:
        connection.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('user_edit_plant', plant_id=plant_id))
    except Error as e:
        connection.rollback()
        flash(f'Error updating plant: {e}', 'danger')
        return redirect(url_for('my_submissions'))
    finally:
        cursor.close()
        connection.close()

@app.route('/plant/<int:plant_id>')
def plant_detail(plant_id):
    """View published plant details"""
    connection = get_db_connection()
    plant = None
    images = None
    varieties = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM plants WHERE id = %s AND status = 'published'", (plant_id,))
        plant = cursor.fetchone()
        if plant:
            cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (plant_id,))
            images = cursor.fetchone()
            varieties = get_plant_varieties(cursor, plant_id)
        cursor.close()
        connection.close()

    if not plant:
        flash('Plant not found!', 'danger')
        return redirect(url_for('index'))

    return render_template('plant_detail.html', plant=plant, images=images, varieties=varieties)

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM admin_users WHERE username = %s", (username,))
            admin = cursor.fetchone()
            cursor.close()
            connection.close()

            if admin and check_password_hash(admin['password'], password):
                session['admin_loggedin'] = True
                session['admin_username'] = username
                flash('Welcome Admin!', 'success')
                return redirect(url_for('admin_dashboard'))

        flash('Invalid username or password!', 'danger')

    return render_template('admin/login.html')

@app.route('/admin/logout')
def admin_logout():
    """Admin logout"""
    session.pop('admin_loggedin', None)
    session.pop('admin_username', None)
    flash('Logged out successfully!', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard - Show all plants grouped by status with search/filter"""
    admin_search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all').strip()
    if status_filter not in ['all', 'pending', 'published', 'rejected']:
        status_filter = 'all'

    connection = get_db_connection()
    pending_plants = []
    published_plants = []
    rejected_plants = []
    stats = {'pending': 0, 'published': 0, 'rejected': 0}

    if connection:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                SUM(status = 'pending') AS pending,
                SUM(status = 'published') AS published,
                SUM(status = 'rejected') AS rejected
            FROM plants
        """)
        stat_row = cursor.fetchone() or {}
        stats = {
            'pending': stat_row.get('pending') or 0,
            'published': stat_row.get('published') or 0,
            'rejected': stat_row.get('rejected') or 0
        }

        def fetch_plants_by_status(status, order_by):
            if status_filter != 'all' and status_filter != status:
                return []

            query = f"""
                SELECT p.*, pi.main_image, pi.leaf_image, pi.fruit_image, pi.flower_image, pi.bark_image, pi.root_image,
                       (
                           SELECT COUNT(*)
                           FROM plants dp
                           WHERE dp.id != p.id
                             AND dp.status = 'published'
                             AND (
                                 LOWER(TRIM(dp.name)) = LOWER(TRIM(p.name))
                                 OR (
                                     p.name IS NOT NULL AND p.name != ''
                                     AND (
                                         LOWER(TRIM(p.name)) LIKE CONCAT('%%', LOWER(TRIM(dp.name)), '%%')
                                         OR LOWER(TRIM(dp.name)) LIKE CONCAT('%%', LOWER(TRIM(p.name)), '%%')
                                     )
                                 )
                                 OR (
                                     p.marathi_name IS NOT NULL AND p.marathi_name != ''
                                     AND LOWER(TRIM(dp.marathi_name)) = LOWER(TRIM(p.marathi_name))
                                 )
                                 OR (
                                     p.hindi_name IS NOT NULL AND p.hindi_name != ''
                                     AND LOWER(TRIM(dp.hindi_name)) = LOWER(TRIM(p.hindi_name))
                                 )
                                 OR (
                                     p.scientific_name IS NOT NULL AND p.scientific_name != ''
                                     AND LOWER(TRIM(dp.scientific_name)) = LOWER(TRIM(p.scientific_name))
                                 )
                             )
                       ) AS duplicate_count
                FROM plants p
                LEFT JOIN plant_images pi ON p.id = pi.plant_id
                WHERE p.status = %s
            """
            params = [status]
            if admin_search:
                query += """
                    AND (
                        p.name LIKE %s OR p.marathi_name LIKE %s OR p.hindi_name LIKE %s
                        OR p.scientific_name LIKE %s OR p.family LIKE %s
                        OR p.plant_type LIKE %s OR p.category LIKE %s OR p.submitted_by LIKE %s
                    )
                """
                term = f"%{admin_search}%"
                params.extend([term] * 8)
            query += f" ORDER BY {order_by}"
            cursor.execute(query, params)
            return cursor.fetchall()

        pending_plants = fetch_plants_by_status('pending', 'p.updated_at DESC')
        published_plants = fetch_plants_by_status('published', 'p.published_at DESC')
        rejected_plants = fetch_plants_by_status('rejected', 'p.updated_at DESC')

        cursor.close()
        connection.close()

    return render_template('admin/dashboard.html', 
                         pending_plants=pending_plants,
                         published_plants=published_plants,
                         rejected_plants=rejected_plants,
                         stats=stats,
                         admin_search=admin_search,
                         status_filter=status_filter)

@app.route('/admin/view/<int:plant_id>')
@admin_required
def admin_view_plant(plant_id):
    """Admin view single plant details - ALL images grouped together"""
    connection = get_db_connection()
    plant = None
    images = None
    duplicate_plants = []
    varieties = []

    if connection:
        cursor = connection.cursor(dictionary=True)

        # Get plant details
        cursor.execute("SELECT * FROM plants WHERE id = %s", (plant_id,))
        plant = cursor.fetchone()

        if plant:
            # Get ALL images for this plant (grouped together)
            cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (plant_id,))
            images = cursor.fetchone()
            varieties = get_plant_varieties(cursor, plant_id)

            cursor.execute("""
                SELECT id, name, marathi_name, hindi_name, scientific_name, status, created_at
                FROM plants
                WHERE id != %s
                  AND status = 'published'
                  AND (
                      LOWER(TRIM(name)) = LOWER(TRIM(%s))
                      OR (
                          %s IS NOT NULL AND %s != ''
                          AND (
                              LOWER(TRIM(%s)) LIKE CONCAT('%%', LOWER(TRIM(name)), '%%')
                              OR LOWER(TRIM(name)) LIKE CONCAT('%%', LOWER(TRIM(%s)), '%%')
                          )
                      )
                      OR (
                          %s IS NOT NULL AND %s != ''
                          AND LOWER(TRIM(marathi_name)) = LOWER(TRIM(%s))
                      )
                      OR (
                          %s IS NOT NULL AND %s != ''
                          AND LOWER(TRIM(hindi_name)) = LOWER(TRIM(%s))
                      )
                      OR (
                          %s IS NOT NULL AND %s != ''
                          AND LOWER(TRIM(scientific_name)) = LOWER(TRIM(%s))
                      )
                  )
                ORDER BY created_at DESC
            """, (
                plant_id,
                plant.get('name'),
                plant.get('name'),
                plant.get('name'),
                plant.get('name'),
                plant.get('name'),
                plant.get('marathi_name'),
                plant.get('marathi_name'),
                plant.get('marathi_name'),
                plant.get('hindi_name'),
                plant.get('hindi_name'),
                plant.get('hindi_name'),
                plant.get('scientific_name'),
                plant.get('scientific_name'),
                plant.get('scientific_name')
            ))
            duplicate_plants = cursor.fetchall()

        cursor.close()
        connection.close()

    if not plant:
        flash('Plant not found!', 'danger')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/view_plant.html', plant=plant, images=images, duplicate_plants=duplicate_plants, varieties=varieties)

@app.route('/admin/edit/<int:plant_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_plant(plant_id):
    """Admin can edit plant details during review."""
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed!', 'danger')
        return redirect(url_for('admin_dashboard'))

    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM plants WHERE id = %s", (plant_id,))
        plant = cursor.fetchone()
        if not plant:
            flash('Plant not found!', 'danger')
            return redirect(url_for('admin_dashboard'))

        cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (plant_id,))
        images = cursor.fetchone()
        varieties = get_plant_varieties(cursor, plant_id)

        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            marathi_name = request.form.get('marathi_name', '').strip()
            hindi_name = request.form.get('hindi_name', '').strip()
            scientific_name = request.form.get('scientific_name', '').strip()
            family = request.form.get('family', '').strip()
            plant_type = request.form.get('plant_type', '').strip()
            category = request.form.get('category', '').strip()
            description = request.form.get('description', '').strip()
            medicinal_uses = request.form.get('medicinal_uses', '').strip()
            nutritional_benefits = request.form.get('nutritional_benefits', '').strip()
            varieties_text = request.form.get('varieties', '').strip()

            if not name or not plant_type or not category:
                flash('Plant name, type, and category are required.', 'danger')
                return redirect(url_for('admin_edit_plant', plant_id=plant_id))
            cursor.execute("""
                UPDATE plants
                SET name = %s, marathi_name = %s, hindi_name = %s, scientific_name = %s,
                    family = %s, plant_type = %s, category = %s, description = %s,
                    medicinal_uses = %s, nutritional_benefits = %s, varieties = %s
                WHERE id = %s
            """, (
                name, marathi_name, hindi_name, scientific_name, family, plant_type, category,
                description, medicinal_uses, nutritional_benefits, varieties_text, plant_id
            ))

            image_updates = {}
            for field_name, _ in IMAGE_FIELDS:
                uploaded = save_uploaded_file(request.files.get(field_name))
                if uploaded:
                    image_updates[field_name] = uploaded

            if image_updates:
                if images:
                    set_clause = ', '.join([f"{field} = %s" for field in image_updates])
                    cursor.execute(
                        f"UPDATE plant_images SET {set_clause} WHERE plant_id = %s",
                        list(image_updates.values()) + [plant_id]
                    )
                else:
                    cursor.execute("""
                        INSERT INTO plant_images (plant_id, main_image, leaf_image, fruit_image, flower_image, bark_image, root_image)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        plant_id,
                        image_updates.get('main_image'),
                        image_updates.get('leaf_image'),
                        image_updates.get('fruit_image'),
                        image_updates.get('flower_image'),
                        image_updates.get('bark_image'),
                        image_updates.get('root_image')
                    ))

            save_varieties_from_form(cursor, plant_id)
            cursor.execute("""
                INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                VALUES (%s, 'edit', %s, 'Plant details edited by admin')
            """, (plant_id, session.get('admin_username', 'admin')))
            connection.commit()
            flash('Plant updated successfully!', 'success')
            return redirect(url_for('admin_view_plant', plant_id=plant_id))

        return render_template(
            'admin/edit_plant.html',
            plant=plant,
            images=images,
            varieties=varieties,
            plant_types=PLANT_TYPES,
            categories=FUNCTIONAL_CATEGORIES
        )
    except ValueError as e:
        connection.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('admin_edit_plant', plant_id=plant_id))
    except Error as e:
        connection.rollback()
        flash(f'Error updating plant: {e}', 'danger')
        return redirect(url_for('admin_view_plant', plant_id=plant_id))
    finally:
        cursor.close()
        connection.close()

@app.route('/admin/publish/<int:plant_id>', methods=['POST'])
@admin_required
def admin_publish(plant_id):
    """Publish a plant"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM plants WHERE id = %s", (plant_id,))
            plant = cursor.fetchone()
            if not plant:
                flash('Plant not found.', 'danger')
                return redirect(url_for('admin_dashboard'))

            duplicate_plant = find_published_duplicate(cursor, plant)
            if duplicate_plant and plant.get('status') != 'published':
                added_varieties = merge_submission_varieties(cursor, plant, duplicate_plant)
                if not added_varieties:
                    flash('A published plant with this name already exists. Reject this submission with a duplicate reason, or add a new variety before publishing.', 'warning')
                    return redirect(url_for('admin_view_plant', plant_id=plant_id))

                merge_reason = f"Accepted as new variety under existing plant: {duplicate_plant['name']}."
                cursor.execute("""
                    UPDATE plants
                    SET status = 'rejected', rejection_reason = %s, published_at = NULL
                    WHERE id = %s
                """, (merge_reason, plant_id))

                cursor.execute("""
                    INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                    VALUES (%s, 'merge_variety', %s, %s)
                """, (
                    plant_id,
                    session.get('admin_username', 'admin'),
                    f"Added varieties to plant ID {duplicate_plant['id']}: {', '.join(added_varieties)}"
                ))

                connection.commit()
                flash(f"New variety added to existing plant '{duplicate_plant['name']}'. Duplicate submission was not published.", 'success')
                return redirect(url_for('admin_view_plant', plant_id=duplicate_plant['id']))

            # Update plant status
            cursor.execute("""
                UPDATE plants 
                SET status = 'published', rejection_reason = NULL, published_at = NOW() 
                WHERE id = %s
            """, (plant_id,))

            # Log the action
            cursor.execute("""
                INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                VALUES (%s, 'publish', %s, 'Plant published by admin')
            """, (plant_id, session.get('admin_username', 'admin')))

            connection.commit()
            flash('✅ Plant published successfully!', 'success')
        except Error as e:
            connection.rollback()
            flash(f'Error publishing plant: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject/<int:plant_id>', methods=['POST'])
@admin_required
def admin_reject(plant_id):
    """Reject a plant"""
    rejection_reason = request.form.get('rejection_reason', '').strip()
    if not rejection_reason:
        flash('Rejection reason is required so the user can understand what to fix.', 'danger')
        return redirect(request.referrer or url_for('admin_dashboard'))

    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # Update plant status
            cursor.execute("""
                UPDATE plants
                SET status = 'rejected', rejection_reason = %s, published_at = NULL
                WHERE id = %s
            """, (rejection_reason, plant_id))

            # Log the action
            cursor.execute("""
                INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                VALUES (%s, 'reject', %s, %s)
            """, (plant_id, session.get('admin_username', 'admin'), f'Plant rejected by admin. Reason: {rejection_reason}'))

            connection.commit()
            flash('❌ Plant rejected!', 'info')
        except Error as e:
            connection.rollback()
            flash(f'Error rejecting plant: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/unpublish/<int:plant_id>', methods=['POST'])
@admin_required
def admin_unpublish(plant_id):
    """Unpublish a plant (move back to pending)"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            cursor.execute("UPDATE plants SET status = 'pending', published_at = NULL WHERE id = %s", (plant_id,))

            cursor.execute("""
                INSERT INTO admin_logs (plant_id, action, admin_username, notes)
                VALUES (%s, 'unpublish', %s, 'Plant unpublished by admin')
            """, (plant_id, session.get('admin_username', 'admin')))

            connection.commit()
            flash('📋 Plant moved back to pending!', 'info')
        except Error as e:
            connection.rollback()
            flash(f'Error: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<int:plant_id>', methods=['POST'])
@admin_required
def admin_delete(plant_id):
    """Permanently delete a plant"""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Get images to delete from filesystem
            cursor.execute("SELECT * FROM plant_images WHERE plant_id = %s", (plant_id,))
            images = cursor.fetchone()

            if images:
                # Delete image files from filesystem
                for img_field in ['main_image', 'leaf_image', 'fruit_image', 'flower_image', 'bark_image', 'root_image']:
                    if images.get(img_field):
                        img_path = os.path.join(UPLOAD_FOLDER, images[img_field])
                        if os.path.exists(img_path):
                            os.remove(img_path)

            cursor.execute("""
                SELECT pvi.filename
                FROM plant_variety_images pvi
                JOIN plant_varieties pv ON pvi.variety_id = pv.id
                WHERE pv.plant_id = %s
            """, (plant_id,))
            for row in cursor.fetchall():
                img_path = os.path.join(UPLOAD_FOLDER, row['filename'])
                if os.path.exists(img_path):
                    os.remove(img_path)

            # Delete plant (cascade will delete images and logs)
            cursor.execute("DELETE FROM plants WHERE id = %s", (plant_id,))

            connection.commit()
            flash('🗑️ Plant deleted permanently!', 'success')
        except Error as e:
            connection.rollback()
            flash(f'Error deleting plant: {e}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/logs')
@admin_required
def admin_logs():
    """View admin action logs"""
    connection = get_db_connection()
    logs = []
    if connection:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT al.*, p.name as plant_name 
            FROM admin_logs al 
            LEFT JOIN plants p ON al.plant_id = p.id 
            ORDER BY al.action_date DESC
        """)
        logs = cursor.fetchall()
        cursor.close()
        connection.close()
    return render_template('admin/logs.html', logs=logs)

@app.route('/admin/dataset')
@admin_required
def admin_dataset():
    """Dataset manager page with statistics and download options"""
    connection = get_db_connection()
    stats = {
        'total_plants': 0,
        'published_plants': 0,
        'pending_plants': 0,
        'total_images': 0
    }
    plants = []

    if connection:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                COUNT(*) AS total_plants,
                SUM(status = 'published') AS published_plants,
                SUM(status = 'pending') AS pending_plants
            FROM plants
        """)
        row = cursor.fetchone()
        if row:
            stats['total_plants'] = row.get('total_plants') or 0
            stats['published_plants'] = row.get('published_plants') or 0
            stats['pending_plants'] = row.get('pending_plants') or 0

        cursor.execute("""
            SELECT
                SUM(main_image IS NOT NULL AND main_image != '') +
                SUM(leaf_image IS NOT NULL AND leaf_image != '') +
                SUM(fruit_image IS NOT NULL AND fruit_image != '') +
                SUM(flower_image IS NOT NULL AND flower_image != '') +
                SUM(bark_image IS NOT NULL AND bark_image != '') +
                SUM(root_image IS NOT NULL AND root_image != '') AS total_images
            FROM plant_images
        """)
        image_row = cursor.fetchone()
        stats['total_images'] = (image_row or {}).get('total_images') or 0
        cursor.execute("SELECT COUNT(*) AS total_variety_images FROM plant_variety_images")
        variety_image_row = cursor.fetchone()
        stats['total_images'] += (variety_image_row or {}).get('total_variety_images') or 0

        cursor.execute("""
            SELECT p.id, p.name, p.marathi_name, p.hindi_name, p.scientific_name, p.plant_type, p.category, p.status,
                   p.created_at, pi.main_image, pi.leaf_image, pi.fruit_image,
                   pi.flower_image, pi.bark_image, pi.root_image,
                   ((pi.main_image IS NOT NULL AND pi.main_image != '') +
                    (pi.leaf_image IS NOT NULL AND pi.leaf_image != '') +
                    (pi.fruit_image IS NOT NULL AND pi.fruit_image != '') +
                    (pi.flower_image IS NOT NULL AND pi.flower_image != '') +
                    (pi.bark_image IS NOT NULL AND pi.bark_image != '') +
                    (pi.root_image IS NOT NULL AND pi.root_image != '')) AS image_count
            FROM plants p
            LEFT JOIN plant_images pi ON p.id = pi.plant_id
            ORDER BY p.created_at DESC
        """)
        plants = cursor.fetchall()

        cursor.close()
        connection.close()

    return render_template('admin/dataset.html', stats=stats, plants=plants)

@app.route('/admin/dataset/download/csv')
@admin_required
def admin_dataset_download_csv():
    """Download dataset metadata as CSV"""
    status_filter = request.args.get('status', 'published')
    if status_filter not in ['published', 'all']:
        status_filter = 'published'

    plants = get_dataset_plants(status_filter)
    csv_content = build_dataset_metadata_csv(plants)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"plant_dataset_metadata_{status_filter}_{timestamp}.csv"

    return send_file(
        io.BytesIO(csv_content.encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )

@app.route('/admin/dataset/download/zip')
@admin_required
def admin_dataset_download_zip():
    """Download images and CSV metadata in one ZIP archive"""
    status_filter = request.args.get('status', 'published')
    if status_filter not in ['published', 'all']:
        status_filter = 'published'

    plants = get_dataset_plants(status_filter)
    csv_content = build_dataset_metadata_csv(plants)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    zip_filename = f"plant_dataset_{timestamp}.zip"

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as dataset_zip:
        dataset_zip.writestr('dataset_metadata.csv', csv_content.encode('utf-8-sig'))
        dataset_zip.writestr(
            'README.txt',
            "Plant Dataset Export\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Filter: {'Published plants only' if status_filter == 'published' else 'All plants'}\n\n"
            "Structure:\n"
            "- dataset_metadata.csv contains plant metadata and image filenames.\n"
            "- images/<Plant_Name>/ contains available plant images grouped by plant.\n"
        )

        connection = get_db_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)
            for plant in plants:
                write_plant_to_dataset_zip(dataset_zip, cursor, plant)
            cursor.close()
            connection.close()

    zip_buffer.seek(0)
    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )

@app.route('/admin/dataset/download/plant/<int:plant_id>')
@admin_required
def admin_dataset_download_single_plant(plant_id):
    """Download one plant with its base and variety images."""
    connection = get_db_connection()
    if not connection:
        flash('Database connection failed!', 'danger')
        return redirect(url_for('admin_dataset'))

    cursor = connection.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.*, pi.main_image, pi.leaf_image, pi.fruit_image, pi.flower_image, pi.bark_image, pi.root_image
        FROM plants p
        LEFT JOIN plant_images pi ON p.id = pi.plant_id
        WHERE p.id = %s
    """, (plant_id,))
    plant = cursor.fetchone()
    if not plant:
        cursor.close()
        connection.close()
        flash('Plant not found!', 'danger')
        return redirect(url_for('admin_dataset'))

    zip_buffer = io.BytesIO()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{safe_dataset_folder_name(plant.get('name'))}_dataset_{timestamp}.zip"
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as dataset_zip:
        dataset_zip.writestr('dataset_metadata.csv', build_dataset_metadata_csv([plant]).encode('utf-8-sig'))
        dataset_zip.writestr('README.txt', f"Single plant dataset export for {plant.get('name')}\n")
        write_plant_to_dataset_zip(dataset_zip, cursor, plant)

    cursor.close()
    connection.close()
    zip_buffer.seek(0)
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=filename)

# ============================================
# CONTEXT PROCESSOR
# ============================================
@app.context_processor
def utility_processor():
    def get_image_url(filename):
        if filename:
            return url_for('static', filename=f'uploads/{filename}')
        return None
    return dict(get_image_url=get_image_url)

# ============================================
# ERROR HANDLERS
# ============================================
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ============================================
# RUN APP
# ============================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
