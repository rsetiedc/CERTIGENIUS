# CertiGenius Setup Guide

> Automated Certificate Generation and Distribution Platform

This guide walks you through setting up and running CertiGenius locally or deploying to Streamlit Cloud.

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
| streamlit | Web framework (primary UI) |
| sqlalchemy==2.0.35 | Database ORM (standalone, no Flask dependency) |
| Pillow | Image processing for certificate generation |
| PyMuPDF | PDF rendering support |
| openpyxl | Excel file parsing (.xlsx) |
| python-dotenv | Environment variable management |
| qrcode[pil] | QR code generation on certificates |
| email-validator | Email validation |

> **Note:** A legacy Flask version also exists (`app.py` + `run.py`) but the **primary interface is Streamlit** (`Home.py`).

---

## Step 4: Configure Email Credentials

Email distribution is **optional** — you can generate and download certificates without configuring it. But to send certificates via email, you need to set up Gmail credentials.

You have **two options** for configuring credentials:

### Option A: `.env` file (recommended for local development)

Copy the example file and edit it:

```bash
cp .env.example .env
```

Open `.env` in your editor and set your values:

```env
# Your Gmail address
MAIL_USERNAME=your-email@gmail.com

# Gmail App Password (NOT your regular password)
# Generate one at: https://myaccount.google.com/apppasswords
MAIL_PASSWORD=your-app-password-here

# Sender name/email (usually same as MAIL_USERNAME)
MAIL_DEFAULT_SENDER=your-email@gmail.com
```

> The `.env` file is automatically loaded by `config.py` when the app starts. It is listed in `.gitignore` so your credentials stay safe.

### Option B: `.streamlit/secrets.toml` (for Streamlit Cloud or local Streamlit)

This is the standard Streamlit way to manage secrets. Edit the file `.streamlit/secrets.toml`:

```toml
MAIL_USERNAME = "your-email@gmail.com"
MAIL_PASSWORD = "your-app-password-here"
MAIL_DEFAULT_SENDER = "your-email@gmail.com"
```

> **Note:** `.streamlit/secrets.toml` is in `.gitignore` and will not be committed. For Streamlit Cloud, add the same keys in your app's **Settings → Secrets** dashboard.

### Getting a Gmail App Password

1. Go to your [Google Account](https://myaccount.google.com/)
2. Navigate to **Security** → **2-Step Verification** (enable it if not already)
3. Go to **Security** → **App Passwords**
4. Select **Mail** as the app and **Other** as the device (name it "CertiGenius")
5. Copy the 16-character password (with spaces) and paste it into your credential file

---

## Step 5: Run the Application

### Streamlit (Primary UI — Recommended)

```bash
streamlit run Home.py
```

The app opens at **http://localhost:8501** in your browser automatically.

To specify a different port:

```bash
streamlit run Home.py --server.port 8501
```

### Flask (Legacy UI)

```bash
python3 run.py
```

The Flask server starts at **http://localhost:5000** (port configurable via `PORT` env var).

---

## Step 6: Verify It Works

Open **http://localhost:8501** in your browser. You should see the **CertiGenius Dashboard** with:

- **Statistics Cards** — Templates, Participants, Batches, Certificates, Sent counts
- **Quick Actions** — Management shortcuts
- **Recent Batches** — Latest 5 batches with status
- **Workflow Guide** — 4-step visual guide

### Navigation (Sidebar)

| Page | Description |
|---|---|
| 📊 Dashboard | Home page with stats and quick actions |
| 📄 Templates | Upload and manage certificate templates |
| 👥 Import Participants | Upload CSV/Excel to create batches |
| 📦 Batches | View all batches and their status |
| ✅ Verify Certificate | Look up certificate authenticity |

---

## Step 7: Usage Walkthrough

### 1. Upload a Template

1. Go to **📄 Templates** in the sidebar
2. Click **Upload Template Group**
3. Enter a group name (e.g., "Summer Workshop")
4. Select one or more certificate design files (PNG, JPG, or PDF)
5. Define **placeholder fields** — comma-separated field names like: `participant_name, prize_position, event_name`
6. Click **Upload**

> 💡 **Template Design Tips:**
> - Create your certificate design in Canva, Photoshop, or any image editor
> - Leave blank spaces where text should appear
> - Upload at high resolution (1200×800 px or larger)
> - Name files by position for auto-detection: `1st_prize.png`, `participation.png`, etc.

### 2. Import Participants

1. Go to **👥 Import Participants** in the sidebar
2. Give your batch a name (e.g., "Summer Workshop 2025")
3. (Optional) Select a template group to associate
4. Upload your CSV or Excel file
5. Click **Upload**

**Required columns (auto-detected):**

| Name | Email | Prize Position |
|---|---|---|
| John Doe | john@example.com | 1st |
| Jane Smith | jane@example.com | 2nd |
| Bob Wilson | bob@example.com | Participation |

**Column name examples:**
- Name: `Name`, `Full Name`, `Participant Name`, `Candidate Name`
- Email: `Email`, `E-mail`, `Email Address`, `Mail`
- Prize: `Prize`, `Prize Position`, `Position`, `Award`, `Rank`, `Result`

Any additional columns (e.g., `Organization`, `Course`) are stored as extra data and can be used as placeholder fields.

### 3. Generate Certificates

1. Go to **📦 Batches** → click a batch to view its detail page
2. Click **🔨 Generate Certificates**
3. The system processes each participant and creates personalized PDF certificates
4. Progress is tracked live — green for success, red for failures

### 4. Distribute & Download

- **📧 Distribute via Email** — Sends each certificate as a PDF attachment with a styled HTML email (requires Gmail credentials)
- **📦 Download All as ZIP** — Downloads all generated certificates in a single ZIP file
- **⬇️ Individual Downloads** — Download each certificate individually

---

## Streamlit Cloud Deployment

1. Push your code to GitHub (ensure `.env` and `.streamlit/secrets.toml` are in `.gitignore`)
2. Go to [Streamlit Cloud](https://share.streamlit.io) and sign in with GitHub
3. Click **New app** → select your repo
4. Set:
   - **Repository:** `your-username/certigenius`
   - **Branch:** `main`
   - **Main file path:** `Home.py`
5. Click **Deploy**
6. After deployment, go to **Settings → Secrets** and add your email credentials:

   ```toml
   MAIL_USERNAME = "your-email@gmail.com"
   MAIL_PASSWORD = "your-app-password-here"
   MAIL_DEFAULT_SENDER = "your-email@gmail.com"
   APP_URL = "https://your-app-name.streamlit.app"
   ```

> **Note:** The free Streamlit Cloud tier puts apps to sleep after 7 days of inactivity. The app will wake up when visited.

---

## Project Structure

```
certigenius/
├── Home.py                    # Streamlit entry point (main UI)
├── app.py                     # Legacy Flask application
├── run.py                     # Legacy Flask entry point
├── config.py                  # Configuration (reads .env + Streamlit secrets)
├── models.py                  # Database models (Streamlit-compatible)
├── requirements.txt           # Python dependencies
├── .env                       # Your local credentials (NOT committed)
├── .env.example               # Credential template
├── .gitignore                 # Git ignore rules
│
├── pages/                     # Streamlit multi-page app
│   ├── __init__.py
│   ├── 1_Templates.py         # Template management page
│   ├── 2_Import_Participants.py  # Participant import page
│   ├── 3_Batches.py           # Batch listing page
│   ├── 4_Batch_Detail.py      # Batch detail + generation + email
│   └── 5_Verify.py            # Certificate verification page
│
├── .streamlit/                # Streamlit configuration
│   ├── config.toml            # Theme, server, browser settings
│   └── secrets.toml           # Your Streamlit secrets (NOT committed)
│
├── utils/
│   ├── __init__.py
│   ├── db.py                  # Database connection (Streamlit-compatible)
│   ├── excel_parser.py        # CSV/XLSX file parser
│   ├── certificate_generator.py  # Certificate PDF generation (Pillow)
│   └── email_sender.py        # Gmail SMTP email distribution
│
├── templates/                 # Legacy Flask HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── templates.html
│   ├── template_detail.html
│   ├── participants.html
│   ├── batches.html
│   ├── batch_detail.html
│   └── error.html
│
├── fonts/                     # Certificate fonts (Montserrat, Niconne)
│   ├── Montserrat-Regular.ttf
│   ├── Montserrat-Bold.ttf
│   └── Niconne-Regular.ttf
│
├── uploads/                   # Uploaded files (auto-created)
│   ├── templates/             # Certificate template images/PDFs
│   └── participants/          # Participant data files
│
└── generated_certificates/    # Generated PDF certificates (auto-created)
```

---

## Troubleshooting

### "Email not configured" Error

Make sure you've set `MAIL_USERNAME`, `MAIL_PASSWORD`, and `MAIL_DEFAULT_SENDER` in one of:
- `.env` file (local development)
- `.streamlit/secrets.toml` (local Streamlit)
- Streamlit Cloud **Settings → Secrets** (cloud deployment)

See [Step 4](#step-4-configure-email-credentials) above for details.

### "Gmail rejected the app password"

- Ensure **2-Step Verification** is enabled on your Google Account
- Generate a fresh App Password at https://myaccount.google.com/apppasswords
- Paste the 16-character password **exactly** as shown (spaces included)

### "Port already in use"

```bash
# Find what's using the port
lsof -i :8501

# Kill it (replace PID with the process ID)
kill -9 <PID>

# Or use a different port
streamlit run Home.py --server.port 8502
```

### "Database errors"

Delete the SQLite database file and restart:

```bash
rm certigenius.db
streamlit run Home.py
```

### "Module not found"

Ensure your virtual environment is activated and dependencies are installed:

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### "Pillow installation fails"

On macOS, you may need additional system libraries:

```bash
brew install libjpeg zlib

# Ubuntu/Debian
sudo apt-get install libjpeg-dev zlib1g-dev
```
