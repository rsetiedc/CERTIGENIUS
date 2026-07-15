# CertiGenius 🏆

> **Automated Certificate Generation and Distribution Platform**

CertiGenius streamlines the process of creating and distributing digital certificates. Upload a template, import participant data, and let CertiGenius handle the rest — generating personalized PDF certificates and delivering them via email automatically.

---

## Features

- **📄 Template Management** — Upload certificate templates in PNG, JPG, or PDF format with customizable placeholder fields. Supports template groups with position-based auto-detection (1st, 2nd, 3rd, Participation).
- **📊 Participant Import** — Upload participant data via CSV or Excel (.xlsx/.xls) files with intelligent column auto-detection.
- **🖨️ Certificate Generation** — Dynamically populate templates with participant names, prize positions, event details, and custom data fields. Includes QR code metadata for verification.
- **📧 Email Distribution** — Send personalized certificates directly to participants' inboxes with styled HTML emails and PDF attachments via Gmail SMTP.
- **📦 Batch ZIP Download** — Download all generated certificates in a single ZIP archive with participant names as filenames.
- **✅ Certificate Verification** — Built-in verification page to authenticate certificates via QR code or direct link.
- **📈 Batch Tracking** — Monitor generation and distribution status with live progress tracking.
- **⬇️ Individual Downloads** — Download any certificate as a PDF at any time.

---

## Quick Start

### 1. Setup

```bash
# Clone the repo
git clone <repository-url>
cd certigenius

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure credentials (optional — for email distribution only)
cp .env.example .env
# Edit .env with your Gmail App Password

# Run the app
streamlit run Home.py
```

Open **http://localhost:8501** in your browser.

### 2. Upload a Template

1. Navigate to **📄 Templates** in the sidebar
2. Click **Upload Template Group**
3. Enter a group name and select your certificate design files (PNG, JPG, or PDF)
4. Define **placeholder fields** — comma-separated field names like: `participant_name, prize_position, event_name`
5. Click **Upload**

> 💡 **Template Design Tips:**
> - Create your certificate design in Canva, Photoshop, or any image editor
> - Leave blank spaces where text should appear
> - Upload at a high resolution (1200×800 px or larger) for best print quality
> - Name files by position for auto-detection: `1st_prize.png`, `participation.png`, etc.

### 3. Import Participants

Prepare participant data in a CSV or Excel file. CertiGenius automatically detects the required columns.

**Required columns (auto-detected):**

| Name | Email | Prize Position |
|---|---|---|
| John Doe | john@example.com | 1st |
| Jane Smith | jane@example.com | 2nd |
| Bob Wilson | bob@example.com | Participation |

> **Column name examples:**
> - Name: `Name`, `Full Name`, `Participant Name`, `Candidate Name`
> - Email: `Email`, `E-mail`, `Email Address`, `Mail`
> - Prize Position: `Prize`, `Prize Position`, `Position`, `Award`, `Rank`, `Result`

**Any additional columns** (e.g., `Organization`, `Course`, `Event`, `Date`) are automatically stored as extra data and can be used as template placeholders.

### 4. Generate Certificates

1. Go to **📦 Batches** → click a batch to view its detail page
2. Click **🔨 Generate Certificates**
3. The system processes each participant, creating personalized PDF certificates
4. Smart text placement detects dashed lines in templates for precise text positioning
5. QR codes are embedded with certificate metadata for verification

### 5. Distribute & Download

- **📧 Distribute via Email** — Each participant receives a styled HTML email with their certificate as a PDF attachment (requires Gmail credentials)
- **📦 Download All as ZIP** — Bulk download all certificates in a single archive
- **⬇️ Individual Downloads** — Download single certificates from the batch detail page

---

## Pages Overview

### 📊 Dashboard (`Home.py`)
- Statistics cards showing counts for templates, participants, batches, certificates, and emails sent
- Quick action buttons for each workflow step
- Recent batches list with status indicators
- Visual 4-step workflow guide

### 📄 Templates (`pages/1_Templates.py`)
- Upload template groups with multiple position-based designs
- Define placeholder fields for dynamic text placement
- View all template groups with file type counts
- Delete unwanted templates

### 👥 Import Participants (`pages/2_Import_Participants.py`)
- Upload CSV or Excel files with auto-column detection
- Name your batch and optionally assign a template group
- Download a sample CSV template
- View recent uploads

### 📦 Batches (`pages/3_Batches.py`)
- View all batches sorted by date
- Status badges with progress indicators
- Click through to batch detail pages

### 📦 Batch Detail (`pages/4_Batch_Detail.py`)
- Batch overview with metrics and template group info
- Participants table with extra data fields
- Certificates table with generation/email status
- Actions: Generate, Email, ZIP Download, Delete
- Individual certificate downloads

### ✅ Verify Certificate (`pages/5_Verify.py`)
- Look up certificate authenticity by ID
- Displays certificate metadata (participant, event, date)
- Accessible via QR code embedded on certificates

---

## Email Configuration

To send certificates via email, configure Gmail SMTP credentials. You have **two options**:

### Local Development: `.env` file
```bash
cp .env.example .env
# Edit .env with your Gmail App Password
```

### Streamlit Cloud: Settings → Secrets
Add these keys to your Streamlit Cloud secrets:
```toml
MAIL_USERNAME = "your-email@gmail.com"
MAIL_PASSWORD = "your-16-char-app-password"
MAIL_DEFAULT_SENDER = "your-email@gmail.com"
APP_URL = "https://your-app-name.streamlit.app"
```

### Getting a Gmail App Password
1. Enable **2-Step Verification** at https://myaccount.google.com/security
2. Go to https://myaccount.google.com/apppasswords
3. Generate an App Password for "Mail" + "Other" device
4. Copy the 16-character password into your credential file

---

## Technical Stack

| Component | Technology |
|---|---|
| Web Framework | **Streamlit** (primary), Flask (legacy) |
| Database | SQLite (default), PostgreSQL-ready via SQLAlchemy |
| Certificate Generation | Pillow (image templates) |
| File Parsing | openpyxl, csv |
| Email | SMTP (Gmail App Passwords) |
| QR Codes | qrcode[pil] |
| Fonts | Montserrat (Google Fonts), Niconne |
| Deployment | Streamlit Cloud, Koyeb (Flask) |

---

## File Locations

| Data | Location |
|---|---|
| Certificate templates | `uploads/templates/` |
| Participant files | `uploads/participants/` |
| Generated certificates | `generated_certificates/<batch_id>/` |
| Database | `certigenius.db` |
| Font files | `fonts/` |

---

## Use Cases

- **🏫 Educational Institutions** — Course completion, academic awards
- **🎪 Event Organizers** — Conference attendance, workshop participation
- **🏆 Competitions** — Hackathon prizes, coding contest winners
- **💼 Corporate Training** — Employee training completion, skill certifications
- **🌐 Webinars** — Attendance certificates for online events

---

## Limitations (Current Version)

- **PDF template editing** — PDF templates generate a new PDF rather than editing the uploaded PDF directly.
- **Gmail only** — Email distribution is configured for Gmail SMTP. Other providers require changes in the credential files.
- **Single user** — No multi-user authentication or role-based access.
- **Streamlit Cloud free tier** — Apps sleep after 7 days of inactivity.

---

## Architecture

CertiGenius follows a modular architecture with Streamlit as the primary interface:

- **`Home.py`** — Streamlit entry point with dashboard
- **`pages/*.py`** — Multi-page Streamlit app (Templates, Import, Batches, Verification)
- **`config.py`** — Configuration loading (`.env` + Streamlit secrets)
- **`models.py`** — SQLAlchemy models (standalone, no Flask dependency)
- **`utils/db.py`** — Streamlit-compatible database connection
- **`utils/excel_parser.py`** — CSV/XLSX parsing with column auto-detection
- **`utils/certificate_generator.py`** — Certificate generation with smart text positioning
- **`utils/email_sender.py`** — Gmail SMTP with styled HTML email templates

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams.

---

## License

This project is provided for educational and internal use.
