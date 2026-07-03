# CertiGenius Setup Guide

> Automated Certificate Generation and Distribution Platform

This guide walks you through setting up and running CertiGenius on your local machine.

---

## Prerequisites

- **Python 3.9+** installed on your system
- **pip** (Python package manager)
- **Git** (optional, for cloning the repository)

Verify your Python installation:

```bash
python3 --version
pip3 --version
```

---

## Step 1: Get the Code

Clone the repository or copy the project files to your local machine.

```bash
git clone <repository-url>
cd certigenius
```

---

## Step 2: Create a Virtual Environment (Recommended)

Isolate the project's dependencies from your system Python:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate
```

Your terminal prompt should now show `(venv)` at the beginning.

---

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all required packages:

| Package | Purpose |
|---|---|
| Flask | Web framework |
| Flask-SQLAlchemy | Database ORM |
| Pillow | Image processing for certificate generation |
| ReportLab | PDF generation |
| openpyxl | Excel file parsing (.xlsx) |
| python-dotenv | Environment variable management |
| gunicorn | Production WSGI server |
| email-validator | Email validation |

---

## Step 4: Configure Environment Variables

Copy the example environment file and update the values:

```bash
cp .env.example .env
# Or edit the existing .env file
```

Open `.env` in your editor and configure the following:

```env
# Flask secret key (change this in production!)
SECRET_KEY=your-secret-key-change-me

# Database (SQLite by default, no changes needed for local dev)
DATABASE_URL=sqlite:///certigenius.db

# --- Email Configuration (Required for sending certificates) ---
# Gmail SMTP settings
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true

# Your Gmail address
MAIL_USERNAME=your-email@gmail.com

# Gmail App Password (NOT your regular password)
# Generate one at: https://myaccount.google.com/apppasswords
MAIL_PASSWORD=your-app-password-here

# Sender name/email (usually same as MAIL_USERNAME)
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

### Getting a Gmail App Password

1. Go to your [Google Account](https://myaccount.google.com/)
2. Navigate to **Security** → **2-Step Verification** (enable it if not already)
3. Go to **Security** → **App Passwords**
4. Select **Mail** as the app and **Other** as the device (name it "CertiGenius")
5. Copy the 16-character password and paste it into `MAIL_PASSWORD` in `.env`

> **Note:** Email sending is optional. You can generate and download certificates without configuring email.

---

## Step 5: Run the Application

### Development Mode (Recommended)

```bash
python3 run.py
```

The server starts at **http://localhost:5000**.

If port 5000 is in use (common on macOS — AirPlay Receiver uses it), start on a different port:

```bash
python3 -c "from app import create_app; app = create_app(); app.run(debug=True, host='0.0.0.0', port=8000)"
```

### Production Mode

```bash
gunicorn -w 4 -b 0.0.0.0:8000 'app:create_app()'
```

---

## Step 6: Verify It Works

Open your browser and navigate to: **http://localhost:5000**

You should see the CertiGenius dashboard with:
- Navigation bar (Dashboard, Templates, Participants, Batches)
- Statistics cards (all showing 0 initially)
- Quick Actions panel
- Workflow Guide

---

## Project Structure

```
certigenius/
├── app.py                    # Main Flask application with all routes
├── run.py                    # Application entry point
├── config.py                 # Configuration (reads from .env)
├── models.py                 # Database models
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (your config)
├── .gitignore                # Git ignore rules
├── utils/
│   ├── __init__.py
│   ├── excel_parser.py       # CSV/XLSX file parser
│   ├── certificate_generator.py  # Certificate PDF generation
│   └── email_sender.py       # Gmail SMTP email distribution
├── templates/
│   ├── base.html             # Layout template
│   ├── dashboard.html        # Dashboard page
│   ├── templates.html        # Template management
│   ├── template_detail.html  # Template detail view
│   ├── participants.html     # Participant upload page
│   ├── batches.html          # Batch listing page
│   ├── batch_detail.html     # Batch detail view
│   └── error.html            # Error pages (404/500)
├── uploads/                  # Uploaded files (auto-created)
│   ├── templates/            # Certificate template files
│   └── participants/         # Participant data files
└── generated_certificates/   # Generated PDF certificates (auto-created)
```

---

## Troubleshooting

### "Port 5000 already in use"

```bash
# Find what's using the port
lsof -i :5000

# Kill it (replace PID with the process ID)
kill -9 <PID>

# Or use a different port
python3 run.py --port 8000
```

### "Pillow installation fails"

On macOS, you may need to install libjpeg and zlib:

```bash
# macOS
brew install libjpeg zlib

# Ubuntu/Debian
sudo apt-get install libjpeg-dev zlib1g-dev
```

### "Database errors"

Delete the SQLite database file and restart:

```bash
rm certigenius.db
python3 run.py
```

### "Module not found"

Ensure your virtual environment is activated and dependencies are installed:

```bash
source venv/bin/activate
pip install -r requirements.txt
```
