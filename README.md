<<<<<<< HEAD
🌿 Plant Information Management System (Enhanced)
A complete Flask-based web application for managing plant information with user submissions, admin review workflow, search & filter, and dataset export capabilities.
✨ Features
User Side
Upload Plants: Submit plant information with images (Main Tree, Leaf, Flower, Fruit, Bark)
Image Preview: Instant preview with labels when uploading
Browse Plants: View all published plants with beautiful cards
🔍 Search & Filter: Search by name, scientific name, family, description + filter by type/category + sort options
Plant Details: Detailed view with image gallery and full information
Admin Side
Dashboard: View all plants grouped by status (Pending, Published, Rejected)
Review Plants: View all images grouped per plant + full info, then Publish or Reject
Activity Logs: Track all admin actions
📊 Dataset Manager:
View dataset statistics (total plants, images, etc.)
Download ZIP (Images + CSV metadata) - Perfect for ML projects
Download CSV only (Metadata) - Lightweight data export
Filter by status (Published only / All plants)
No Data Entry: Admin only reviews - all data comes from users
🗄️ Database Schema (MySQL)
Tables
plants - All plant information (user-submitted)
plant_images - All images per plant (grouped together)
admin_logs - Admin action tracking
admin_users - Admin login credentials
🚀 Setup Instructions
1. Install Dependencies
bash
Copy
pip install -r requirements.txt
2. Configure MySQL
Edit config.py with your MySQL credentials:
Python
Copy
MYSQL_HOST = 'localhost'
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'your_password'
MYSQL_DB = 'plant_system'
3. Initialize Database
bash
Copy
python init_database.py
4. Run the Application
bash
Copy
python app.py
5. Access the Application
User Portal: http://127.0.0.1:5000/
Admin Panel: http://127.0.0.1:5000/admin/login
Default Admin: username: admin | password: admin123
📁 Project Structure
plain
Copy
plant_system/
├── app.py                 # Main Flask application (ENHANCED)
├── config.py              # Configuration settings
├── init_database.py       # Database initialization
├── database.sql           # SQL schema
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── static/
│   ├── css/              # Stylesheets
│   ├── js/               # JavaScript files
│   └── uploads/          # Uploaded images
└── templates/
    ├── base.html         # Base template
    ├── index.html        # Homepage (WITH SEARCH & FILTER)
    ├── upload.html       # Plant upload form
    ├── plant_detail.html # Public plant detail
    ├── 404.html          # Error page
    ├── 500.html          # Error page
    └── admin/
        ├── login.html      # Admin login
        ├── dashboard.html  # Admin dashboard
        ├── view_plant.html # Review plant (images grouped)
        ├── logs.html       # Activity logs
        └── dataset.html    # 📊 DATASET MANAGER (NEW!)
🔍 Search & Filter Features (NEW)
User Homepage
Search Box: Search across name, scientific name, family, description, medicinal uses, nutritional benefits
Plant Type Filter: Tree, Herb, Shrub, Grass, Climber, Creeper
Category Filter: Fruit, Medicinal, Flowering, Vegetable, Ornamental, Timber, Spice
Sort Options: Newest First, Oldest First, Name A-Z, Name Z-A
Active Filter Tags: Shows currently applied filters
Results Count: Displays "Showing X of Y plants"
Clear Filters: One-click reset all filters
📊 Dataset Export Features (NEW)
Admin Dataset Manager (/admin/dataset)
Statistics Cards: Total plants, published, pending, total images
ZIP Download Options:
Published plants only (with images + CSV)
All plants (with images + CSV)
CSV Download Options:
Published plants metadata only
All plants metadata only
Dataset Preview Table: View all plants with image counts and status
Organized ZIP Structure:
plain
Copy
plant_dataset_20240115_120000.zip
├── dataset_metadata.csv
├── README.txt
└── images/
    ├── Neem_Tree/
    │   ├── main_image_xxx.jpg
    │   ├── leaf_image_xxx.jpg
    │   └── ...
    └── Mango_Tree/
        ├── main_image_xxx.jpg
        └── ...
🔧 Key Features Explained
Image Upload Flow
User clicks upload box → File picker opens
Select image → Instant preview appears with label
Click × button to remove image
Main Tree Image is required, others are optional
Admin Review Flow
User submits plant → Status: Pending
Admin clicks Review → Sees:
Main Tree Image (large display)
Other images (Leaf, Flower, Fruit, Bark) in grid
All plant information in detail card
Admin clicks Publish → Plant goes live
Or clicks Reject → Plant declined
Dataset Creation Flow
Users upload vegetable/plant images with metadata
Admin reviews and publishes quality submissions
Admin goes to Dataset Manager
Clicks Download ZIP → Gets organized dataset
Use dataset for ML training, research, or sharing
🎨 UI/UX Features
Animated navbar with scroll effect
Floating leaf animations on homepage
Card hover effects (scale + shadow)
Scroll-triggered fade-in animations
Professional green theme
Fully responsive (mobile friendly)
Admin sidebar with smooth transitions
⚠️ Important Notes
Admin CANNOT add plant data manually - only reviews user submissions
All plant info + images are submitted by users only
Images are saved in static/uploads/ folder
Database uses MySQL with proper foreign key relationships
Dataset export creates ZIP in memory (no temp files needed)
📝 License
Open source project for educational purposes.
=======
# Image_Dataset_Management_-_Verification_Platform-
>>>>>>> 77f4c6426c14afe841134c68838166d29df8b5a7
