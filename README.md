# 📬 Email Automation & Reminder System

[![Python Version](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Framework](https://img.shields.io/badge/Framework-Modular%20Python%20%7C%20Streamlit-brightgreen.svg)]()
[![Safety Mode](https://img.shields.io/badge/Safety-Dry--Run%20Enabled-success.svg)]()
[![Testing](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)]()

A modular, beginner-friendly Python application that reads contacts and reminders from CSV files, validates email addresses, personalizes dynamic email templates, manages schedules and recurrence in the `Asia/Kolkata` (IST) timezone, safely simulates email dispatches in dry-run mode, and provides an interactive Streamlit dashboard.

---

## 📖 Table of Contents
- [Problem Statement](#-problem-statement)
- [Key Features](#-key-features)
- [Technology Stack](#-technology-stack)
- [Folder Structure](#-folder-structure)
- [How Dry-Run Mode Works](#-how-dry-run-mode-works)
- [Installation & Setup](#-installation--setup)
- [Configuration Instructions](#-configuration-instructions)
- [How to Run the Application](#-how-to-run-the-application)
- [Sample Outputs](#-sample-outputs)
- [Screenshots & Visuals](#-screenshots--visuals)
- [Automated Testing](#-automated-testing)
- [Future Improvements](#-future-improvements)

---

## 🎯 Problem Statement

Manual notification workflows and client follow-ups are time-consuming, prone to human error, and difficult to audit. Furthermore, beginner developers building email automation systems often risk accidentally spamming live addresses or hardcoding sensitive credentials into their repositories.

The **Email Automation & Reminder System** solves this by offering:
1. A **safe-by-default sandbox** that simulates dispatches without contacting live SMTP servers.
2. An **automated personalization engine** that dynamically injects contact details and reminder specifics into email templates.
3. A **scheduling and recurrence system** that tracks due dates and prevents duplicate sends.
4. An **intuitive user interface** allowing users to inspect datasets, preview rendered emails, trigger simulations, and export audit reports with one click.

---

## ✨ Key Features

- **Robust Contact Management**:
  - Ingests contacts using Pandas from `data/contacts.csv`.
  - Performs RFC-compliant email address validation using regex.
  - Automatically handles missing contact names with friendly fallbacks (`Valued Contact`).
  - Safely flags and skips malformed email addresses with clear warnings.

- **Dynamic Template Personalization**:
  - Loads templates with `{name}`, `{subject}`, `{message}`, and `{date}` placeholders from `templates/email_template.txt`.
  - Intelligently replaces tokens without throwing unhandled exceptions if variables are omitted.
  - Separates email subject headers from the message body for clean rendering.

- **Timezone-Aware Scheduling & Recurrence**:
  - Uses `Asia/Kolkata` (IST) timezone for schedule calculations and due-date evaluations.
  - Supports both **one-time** and recurring (**daily**, **weekly**) reminders.
  - Features an execution history tracker (`outputs/processed_reminders.json`) to prevent duplicate email dispatches.
  - Integrates with the `schedule` library for continuous polling and execution.

- **Security & Safety Guardrails**:
  - **Dry-Run by Default**: Safe simulation mode prevents accidental network/SMTP calls.
  - **Double-Lock Protection**: Actual email transmission requires both `DRY_RUN=False` and `ENABLE_ACTUAL_SENDING=True`.
  - **Strict Recipient Whitelist**: When live mode is activated, only addresses in `ALLOWED_TEST_RECIPIENTS` are permitted.
  - **Zero Password Leaks**: All credentials are read from environment variables (`.env`); no secrets are logged or committed.

- **Audit Reporting & Dual Logging**:
  - Outputs detailed execution records to `outputs/*.csv` capturing recipient, subject, status (`SIMULATED`, `SENT`, `FAILED`, `SKIPPED`), timestamp, and diagnostics.
  - Maintains a continuous, formatted activity stream in `logs/email_system.log`.

- **Interactive Streamlit Dashboard**:
  - Responsive visual KPI cards showing total contacts, total reminders, due items, upcoming items, and completed tasks.
  - Interactive email preview selector.
  - One-click safe simulation launcher with visual progress indicators.
  - Instant CSV audit report download button.

---

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| **Python 3.9+** | Core programming language |
| **Pandas** | High-performance data ingestion, manipulation, and validation |
| **smtplib & email.message** | Secure SMTP client and MIME email message construction |
| **Schedule** | Lightweight, human-friendly recurring job scheduling |
| **Pytz / Datetime** | Timezone parsing and date comparison (`Asia/Kolkata`) |
| **Streamlit** | Interactive, responsive web dashboard |
| **Python-Dotenv** | Secure environment configuration and secrets management |
| **Pytest** | Automated unit and integration testing suite |

---

## 📁 Folder Structure

```text
Email-Automation-Reminder-System/
├── data/
│   ├── contacts.csv                # Sample contacts dataset (valid & invalid test cases)
│   └── reminders.csv               # Sample reminders with dates, frequencies & recipients
├── templates/
│   └── email_template.txt          # Reusable email template with dynamic placeholders
├── src/
│   ├── __init__.py                 # Package root exposing public classes & utilities
│   ├── contact_manager.py          # CSV loading, regex email validation & name handling
│   ├── email_template.py           # Template loading, token parsing & safe rendering
│   ├── email_sender.py             # SMTP dispatcher with dry-run default & security guards
│   ├── scheduler.py                # Asia/Kolkata scheduling, recurrence & duplicate tracker
│   ├── report_generator.py         # CSV audit report generator and status metrics
│   └── logger.py                   # Centralized dual console/file logging (logs/)
├── tests/
│   └── test_email_system.py        # 7 automated unit tests covering all core features
├── outputs/                        # Generated audit reports & duplicate tracking state
│   ├── processed_reminders.json    # Duplicate prevention history
│   └── .gitkeep                    # Directory persistence for version control
├── logs/                           # System activity logs
│   ├── email_system.log            # Detailed operational log records
│   └── .gitkeep
├── images/                         # Project screenshots and diagrams
├── docs/                           # Documentation and guides
├── app.py                          # Interactive Streamlit dashboard application
├── main.py                         # Command-Line Interface (CLI) entry point
├── requirements.txt                # Strictly required external dependencies
├── .env.example                    # Sample environment configuration template
├── .gitignore                      # Git exclusion rules for secrets, caches, and logs
└── README.md                       # Comprehensive project documentation
```

---

## 🛡️ How Dry-Run Mode Works

```
                                [ Dispatch Trigger ]
                                         │
                                         ▼
                               Is DRY_RUN == True?
                                ╱               ╲
                         (YES) ╱                 ╲ (NO)
                              ▼                   ▼
                 [ SAFE SIMULATION ]    Check ENABLE_ACTUAL_SENDING == True?
                 - No network calls               │
                 - No SMTP connection      Is recipient in ALLOWED_TEST_RECIPIENTS?
                 - Logs [SIMULATION]              │
                 - Records in CSV Report   [ LIVE SMTP TRANSMISSION ]
```

1. **Default State**: In both CLI (`main.py`) and Web Dashboard (`app.py`), dry-run simulation mode is permanently enabled by default.
2. **Simulation Execution**: Instead of contacting an external SMTP server, the system:
   - Validates the recipient's email syntax.
   - Matches and personalizes the message with recipient's name and reminder details.
   - Logs the simulated delivery event to `logs/email_system.log`.
   - Records the outcome as `SIMULATED` in the audit report.
3. **Live Mode Double-Lock**: To prevent unintended email distribution:
   - `DRY_RUN` must be explicitly set to `False` (via `.env` or `--live`).
   - `ENABLE_ACTUAL_SENDING` must be explicitly toggled to `True`.
   - The recipient's email address must match an entry in `ALLOWED_TEST_RECIPIENTS`.
   - If any condition fails, transmission is safely aborted with `SKIPPED_UNAUTHORIZED`.

---

## ⚙️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/Email-Automation-Reminder-System.git
cd Email-Automation-Reminder-System
```

### 2. Set Up a Virtual Environment

**On Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🔐 Configuration Instructions

1. Copy `.env.example` to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and review the configuration:
   ```ini
   # Safety First (Default: Simulation Mode)
   DRY_RUN=True
   ENABLE_ACTUAL_SENDING=False

   # Whitelist for Live Testing
   ALLOWED_TEST_RECIPIENTS=tester1@example.com,tester2@example.com

   # SMTP Credentials (Required only for live sending)
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SENDER_NAME="Automated Reminder System"
   SENDER_EMAIL=your_email@gmail.com
   SMTP_PASSWORD=your_app_password_here

   # Regional Timezone
   APP_TIMEZONE=Asia/Kolkata
   ```
> [!NOTE]
> `.env` is listed in `.gitignore` and will never be committed to your repository.

---

## 🚀 How to Run the Application

### Option A: Interactive Streamlit Dashboard

Launch the browser-based dashboard:
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to:
- View real-time KPI metrics.
- Inspect and search contacts.
- Preview personalized email templates.
- Click **"Run Safe Simulation Now"** to test the entire pipeline.
- Click **"Download CSV Report"** to export audit records.

---

### Option B: Command-Line Interface (CLI)

The CLI offers multiple convenient flags:

#### 1. Process Due Reminders (Default Run)
Checks current time in `Asia/Kolkata`, finds due reminders, personalizes templates, simulates delivery, and exports a report:
```bash
python main.py
```

#### 2. Simulate All Reminders (Demo Full Batch)
Processes all reminders in `data/reminders.csv` to verify end-to-end functionality:
```bash
python main.py --run-all
```

#### 3. Display Contacts and Validation Status
```bash
python main.py --show-contacts
```

#### 4. Display Reminders and Current Status
```bash
python main.py --show-reminders
```

#### 5. Run Continuous Background Scheduler
Polls for due reminders at regular intervals (default: every 10 seconds):
```bash
python main.py --schedule --interval 10
```

#### 6. Reset Duplicate Execution Tracker
Clears historical records so reminders can be safely re-tested:
```bash
python main.py --reset-tracker
```

---

## 📊 Sample Outputs

### 1. CLI Execution Output (`python main.py --run-all`)
```text
===========================================================================
       EMAIL AUTOMATION & REMINDER SYSTEM - CLI INTERFACE
               Timezone: Asia/Kolkata (IST)
===========================================================================

[DEMO MODE] Processing all 7 reminders in dataset:

Processing 7 reminder(s)...
 -> [REM-001] To: alice.johnson@example.com | Subject: Project Milestone Review
 -> [REM-002] To: bob.smith@example.com | Subject: Upcoming Team Sync
 -> [REM-003] To: charlie.davis@example.com | Subject: Invoice Payment Reminder
 -> [REM-004] To: diana.prince@example.com | Subject: System Maintenance Notice
 -> [REM-005] To: ethan.hunt@example.com | Subject: Quarterly Goals Check-in
 -> [REM-006] To: frank.nameless@example.com | Subject: Account Profile Verification
 -> [REM-007] To: invalid-email-address-format | Subject: System Test Reminder

Batch processing finished: 6/7 processed successfully.

Audit Report generated: outputs\cli_run_all_report.csv
```

### 2. Audit Report CSV (`outputs/cli_run_all_report.csv`)
| recipient_name | recipient_email | subject | reminder_date_time | status | error_message |
|---|---|---|---|---|---|
| Alice Johnson | alice.johnson@example.com | Project Milestone Review | 2026-11-22 09:00:00 | SIMULATED | |
| Bob Smith | bob.smith@example.com | Upcoming Team Sync | 2026-11-22 15:30:00 | SIMULATED | |
| Valued Contact | frank.nameless@example.com | Account Profile Verification | 2026-11-22 12:00:00 | SIMULATED | |
| Unknown | invalid-email-address-format | System Test Reminder | 2026-11-22 10:00:00 | SKIPPED_INVALID_EMAIL | Invalid email format |

---

## 📸 Screenshots & Visuals

The Streamlit dashboard (`app.py`) provides a 5-tab interface:
1. **Reminders & Schedules**: Interactive table with status filter and status breakdown chart.
2. **Contacts Directory**: Searchable directory displaying validation state (`Valid` vs `Invalid Email`).
3. **Template & Live Preview**: Real-time side-by-side view of the raw template and personalized email output.
4. **Safe Simulation Runner**: One-click simulation with real-time progress bar and results table.
5. **Reports & Activity Logs**: In-browser report viewer, one-click CSV download, and log stream.

*(Screenshots can be saved into the `images/` directory and referenced here for your portfolio presentation).*

---

## 🧪 Automated Testing

A dedicated test suite is included in `tests/test_email_system.py` covering all core components:
1. `test_contact_loading_and_email_validation`: Verifies CSV parsing, regex validation, and default name fallbacks.
2. `test_template_personalization_and_fallback`: Tests token substitution and missing variable safety.
3. `test_datetime_and_timezone_handling`: Tests timezone localization to `Asia/Kolkata`.
4. `test_due_reminder_identification`: Evaluates past due vs upcoming reminders.
5. `test_dry_run_simulation_safety`: Asserts that `EmailSender` performs no live socket/network calls.
6. `test_duplicate_prevention_tracker`: Verifies execution history persistence and duplicate suppression.
7. `test_report_generator_and_csv_export`: Validates report columns and CSV file creation.

Run tests using pytest:
```bash
python -m pytest tests/test_email_system.py -v
```

**Results:**
```text
tests/test_email_system.py::test_contact_loading_and_email_validation PASSED [ 14%]
tests/test_email_system.py::test_template_personalization_and_fallback PASSED [ 28%]
tests/test_email_system.py::test_datetime_and_timezone_handling PASSED   [ 42%]
tests/test_email_system.py::test_due_reminder_identification PASSED      [ 57%]
tests/test_email_system.py::test_dry_run_simulation_safety PASSED        [ 71%]
tests/test_email_system.py::test_duplicate_prevention_tracker PASSED     [ 85%]
tests/test_email_system.py::test_report_generator_and_csv_export PASSED  [100%]

============================== 7 passed in 2.45s ==============================
```

---

## 🔮 Future Improvements

- [ ] **Rich HTML Email Support**: Add responsive HTML templates with inline styles and action buttons.
- [ ] **Database Persistence**: Migrate reminder tracking from JSON/CSV to SQLite / PostgreSQL.
- [ ] **Webhook & Slack Notifications**: Support multi-channel notifications (Slack, Discord, SMS via Twilio).
- [ ] **Custom Attachment Support**: Enable attaching files or personalized PDF invoices to reminders.
- [ ] **OAuth2 Authentication**: Implement Google/Microsoft OAuth2 token-based SMTP authentication.

---

## 📄 License
This project is open-source and free to use for educational, personal, and portfolio purposes.
