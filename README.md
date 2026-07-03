# CertiGenius 🏆

> **Automated Certificate Generation and Distribution Platform**

CertiGenius streamlines the process of creating and distributing digital certificates. Upload a template, import participant data, and let CertiGenius handle the rest — generating personalized PDF certificates and delivering them via email automatically.

---

## Features

- **📄 Template Management** — Upload certificate templates in PNG, JPG, or PDF format with customizable placeholder fields
- **📊 Participant Import** — Upload participant data via CSV or Excel (.xlsx/.xls) files with automatic column detection
- **🖨️ Certificate Generation** — Dynamically populate templates with participant names, prize positions, and custom data
- **📧 Email Distribution** — Send personalized certificates directly to participants' Gmail inboxes with styled HTML emails
- **📈 Batch Tracking** — Monitor generation and distribution status with progress tracking
- **⬇️ Individual Downloads** — Download any certificate as a PDF at any time

---

## Quick Start

### 1. Setup

Follow the detailed [Setup Guide](SETUP.md) to install dependencies and configure the application.

```bash
# Install dependencies
pip install -r requirements.txt

# Configure .env with your settings
# Then run
python3 run.py
```

Open **http://localhost:5000** in your browser.

### 2. Upload a Template

1. Navigate to **Templates** in the navigation bar
2. Click **Upload Template**
3. Select your certificate design (PNG, JPG, or PDF)
4. Define **placeholder fields** — comma-separated field names like: `participant_name, prize_position, event_name`
5. Click **Upload**

> 💡 **Template Design Tips:**
> - Create your certificate design in Canva, Photoshop, or any image editor
> - Leave blank spaces where text should appear
> - Upload at a high resolution (1200x800 px or larger) for best print quality
> - Use a simple, clean background so text is readable

### 3. Import Participants

Prepare your participant data in a CSV or Excel file. CertiGenius automatically detects the required columns.

**Required columns (names are auto-detected):**

| Name | Email | Prize Position |
|---|---|---|
| John Doe | john@example.com | 1st |
| Jane Smith | jane@example.com | 2nd |
| Bob Wilson | bob@example.com | Participation |
| Alice Brown | alice@example.com | 3rd |

> **Column name examples:**
> - Name: `Name`, `Full Name`, `Participant Name`, `Candidate Name`
> - Email: `Email`, `E-mail`, `Email Address`, `Mail`
> - Prize Position: `Prize`, `Prize Position`, `Position`, `Award`, `Rank`, `Result`

**Any additional columns** in your file are automatically stored as extra data and can be used as placeholder fields in your templates.

#### Upload Steps:

1. Go to **Participants** → **Import Participants**
2. Give your batch a name (e.g., "Summer Workshop 2025")
3. (Optional) Select a template to associate with this batch
4. Upload your CSV or Excel file
5. Click **Upload**

You'll be redirected to the **Batch Detail** page showing all imported participants.

### 4. Generate Certificates

1. Go to the **Batch Detail** page for your batch
2. Click **Generate Certificates**
3. The system processes each participant, creating personalized PDF certificates
4. Progress is tracked — green checkmarks indicate success, red for failures

### 5. Distribute Certificates

#### Via Email (requires Gmail SMTP configuration)

1. On the **Batch Detail** page, click **Distribute via Email**
2. Each participant receives a beautifully styled HTML email with their certificate attached as a PDF

> **Note:** You must configure `MAIL_USERNAME` and `MAIL_PASSWORD` in your `.env` file first. See the [Setup Guide](SETUP.md#step-4-configure-environment-variables) for instructions on generating a Gmail App Password.

#### Via Download

- **Individual download:** Click the download icon next to any certificate in the batch detail table
- **Bulk download:** Generate all certificates, then download them from the `generated_certificates/` folder

---

## Workflow Overview

```
┌─────────────┐     ┌─────────────────┐     ┌────────────────────┐     ┌──────────────────┐
│  1. Upload   │ ──→ │  2. Import      │ ──→ │  3. Generate       │ ──→ │  4. Distribute   │
│   Template   │     │   Participants  │     │   Certificates     │     │   via Email      │
└─────────────┘     └─────────────────┘     └────────────────────┘     └──────────────────┘
```

---

## Page-by-Page Guide

### Dashboard (`/`)

- **Statistics Cards** — Quick overview of templates, participants, batches, and certificates sent
- **Quick Actions** — Shortcuts to manage templates, upload participants, or view batches
- **Recent Batches** — Shows your 5 most recent batches with status and progress
- **Workflow Guide** — Visual 4-step guide to using the platform

### Templates (`/templates`)

- **Upload a template** with drag-and-drop support
- **Define placeholders** — comma-separated field names that will be replaced with participant data
- **View all templates** in a grid with file type, date, and placeholder tags
- **Delete templates** you no longer need
- **Click a template** to see its details

### Participants (`/participants/upload`)

- **Import participants** from CSV or Excel files
- **Name your batch** for easy identification
- **Assign a template** to the batch (optional, can be done later)
- **Download a sample CSV** to see the expected format
- **View recent batches** in the sidebar

### Batches (`/batches`)

- **View all your batches** sorted by date (newest first)
- **See batch status** at a glance (Pending, Generating, Generated, Distributing, Completed, Failed)
- **Progress bars** show how many certificates have been processed
- **Click a batch** to see its full details

### Batch Detail (`/batches/<id>`)

- **Batch overview** with name, template, status, and progress
- **Participants table** — all imported participants with their details
- **Certificates table** — generation status for each participant
- **Actions:**
  - **Generate Certificates** — populate templates with participant data
  - **Distribute via Email** — send certificates to all participants
  - **Delete Batch** — remove the batch and all its certificates
- **Download individual certificates** by clicking the download button

---

## Data Format Reference

### Sample CSV

```csv
Name,Email, Prize Position, Organization, Course
Alice Johnson,alice@example.com,1st,Apex Tech,Advanced Python
Bob Smith,bob@example.com,2nd,DataCorp,Machine Learning
Carol Davis,carol@example.com,Participation,WebStudio,Frontend Dev
```

### Sample Excel (.xlsx)

Create an Excel file with the same column structure. Any additional columns (like "Organization" and "Course" above) are stored as extra data and can be used as template placeholders.

---

## Use Cases

- **🏫 Educational Institutions** — Course completion certificates, academic awards
- **🎪 Event Organizers** — Conference attendance, workshop participation
- **🏆 Competitions** — Hackathon prizes, coding contest winners
- **💼 Corporate Training** — Employee training completion, skill certifications
- **🌐 Webinars** — Attendance certificates for online events

---

## Technical Stack

| Component | Technology |
|---|---|
| Backend | Python / Flask |
| Database | SQLite (default), PostgreSQL-ready |
| Templates | Jinja2 |
| Certificate Generation | Pillow (image), ReportLab (PDF) |
| File Parsing | openpyxl, csv |
| Email | SMTP (Gmail) |
| Styling | Bootstrap 5, Google Fonts (Inter) |

---

## Architecture

CertiGenius follows a modular architecture:

- **app.py** — Main Flask application with all route handlers
- **models.py** — SQLAlchemy models: `Template`, `Participant`, `CertificateBatch`, `Certificate`
- **utils/excel_parser.py** — Parses CSV/XLSX files with intelligent column detection
- **utils/certificate_generator.py** — Generates certificates using Pillow (image templates) or ReportLab (PDF templates)
- **utils/email_sender.py** — Sends certificates via Gmail SMTP with formatted HTML email bodies

### Database Schema

```
Template ──┐
            ├── CertificateBatch ──┐
            │                      ├── Participant
            │                      └── Certificate
            └── Certificate
```

---

## File Locations

| Data | Location |
|---|---|
| Uploaded templates | `uploads/templates/` |
| Uploaded participant files | `uploads/participants/` |
| Generated certificates | `generated_certificates/<batch_id>/` |
| Database | `certigenius.db` |

---

## Limitations (Current Version)

- **PDF template editing** — PDF templates generate a new PDF rather than editing the uploaded PDF directly. For advanced PDF template support, consider using PyMuPDF.
- **Authentication** — No user authentication is implemented. Recommended for local/internal network use.
- **Gmail only** — Email distribution is configured for Gmail SMTP. Other providers require configuration changes in `.env`.
- **Single user** — No multi-user or role-based access control.

---

## License

This project is provided for educational and internal use.
