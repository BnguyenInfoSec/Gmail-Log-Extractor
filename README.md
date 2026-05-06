# Gmail to Google Drive Log Exporter

## Overview

This project automates the extraction and organization of email-based logs from Gmail into structured `.txt` files stored in Google Drive.

It was built to replace manual workflows (e.g., screenshots and manual uploads) with a repeatable, automated pipeline.

---

## Features

* Connects to Gmail via OAuth2
* Filters emails by sender and query
* Parses email content (supports plain text and HTML)
* Excludes replies and forwarded messages
* Saves logs as `.txt` files organized by:

  * Year → Month
* Uploads logs to a specified Google Drive folder
* Avoids duplicates by checking existing logs per day
* Supports:

  * **Full historical backfill**
  * **Weekly incremental updates**

---

## Folder Structure (Google Drive)

```
Root Folder/
├── 2025/
│   ├── 12-December/
│   └── ...
├── 2026/
│   ├── 01-January/
│   └── ...
```

---

## Configuration

Edit the following variables in the script:

```python
TARGET_SENDER = "example@example.com"
RUN_MODE = "weekly"   # "weekly" or "full"
WEEKLY_DAYS_BACK = 7

DRIVE_ROOT_FOLDER_ID = "YOUR_DRIVE_FOLDER_ID"
```

### Modes

* `full` → processes all matching emails (used for initial backfill)
* `weekly` → processes only recent emails (default: last 7 days)

---

## Setup

### 1. Install dependencies

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib beautifulsoup4
```

### 2. Google Cloud Setup

* Create a project in Google Cloud Console
* Enable:

  * Gmail API
  * Google Drive API
* Create OAuth 2.0 credentials (Desktop App)
* Download and save as:

```
credentials.json
```

---

## Usage

### Run script

```bash
python Gmail_to_Gdrive_export.py
```

First run will prompt for Google authentication.

---

## Automation (Weekly)

Use Windows Task Scheduler or cron to run:

```bash
python Gmail_to_Gdrive_export.py
```

Recommended schedule:

* Weekly (e.g., Sunday night)

---

## Security Notes

This repository does **not** include:

* `credentials.json`
* `token.json`
* exported logs

Make sure your `.gitignore` includes:

```
credentials.json
token.json
exported_logs/
venv/
```

---

## Example Output

```
Saved locally: exported_logs/2026/05-May/2026-05-10_log.txt
Uploaded to Drive: 2026-05-10_log.txt
Skipped existing TXT log: 2026-05-09
```

---

## Future Improvements

* CLI arguments instead of hardcoded config
* Logging system instead of print statements
* Containerization (Docker)
* Alerting for failed runs
* Support for multiple email sources

---

## Author

Built as part of a workflow automation project focused on improving operational efficiency and reducing manual data handling.

## Security Alignment (NIST SP 800-53)

This project supports standardized audit logging and record retention practices aligned with NIST SP 800-53 controls:

* **AU-2: Event Logging**
  Ensures relevant system events (e.g., login failures) are captured and preserved in a structured format.

* **AU-6: Audit Record Review, Analysis, and Reporting**
  Enables consistent review and analysis by transforming email-based alerts into organized, searchable log files.

* **AU-9: Protection of Audit Information**
  Supports integrity and availability of audit data by storing logs in a centralized and controlled Google Drive location.

By automating log extraction and organization, this tool reduces the risk of missed events and improves audit readiness.

