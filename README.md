# PDF Auto Rename (DASURECO)

An automated OCR-powered web application for batch processing, matching, and renaming official receipts and invoices for **Davao del Sur Electric Cooperative, Inc. (DASURECO)**.

The system extracts text and amounts from single- or multi-page receipt PDFs, performs fuzzy matching against IEMOP/WESM collection reports, determines the correct billing period, and standardizes file names.

---

## Key Features

- **FastAPI Web Application**: Fast, zero-install client interface with real-time WebSocket progress updates.
- **High-Accuracy OCR**: Powered by PaddleOCR for local text recognition on printed and thermal receipts.
- **Smart Receipt Matching**: Multi-metric fuzzy matching via RapidFuzz (token sort, partial ratios, prefix detection) cross-referenced against expected line amounts.
- **Dynamic Excel Ingestion**: Automatically detects column layouts across IEMOP collection reports (prioritizing the `FOR OR` worksheet).
- **Windows Explorer Integration**: Seamlessly browse local drives and SMB network shares (`\\10.0.0.9\...`) via native Windows folder picker dialogs.
- **Fail-Safe Processing**:
  - Matched receipts are renamed using standard naming rules.
  - Unmapped billing periods are safely routed to `<Output>\Unknown Billing Period`.
  - Non-receipts or low-confidence pages are isolated to `<Output>\Failed`.
- **Excel Lock Tolerance**: Active master lists persist across sessions even if the original Excel spreadsheet is open and locked by Microsoft Excel.

---

## Standard Output Format

Renamed files adhere to the standardized naming scheme:
```
SI_DASURECO_<STL_ID>_<BILLING_NUMBER>_<BILLING_PERIOD>_<DATE>.pdf
```
**Example**:
```
SI_DASURECO_TAFTHEC_0057514_0526_20260930.pdf
```

---

## System Requirements

- **Operating System**: Windows 10/11 (or Linux / macOS)
- **Python**: Version 3.10 to 3.12 (64-bit recommended)
- **Visual C++ Redistributable**: [Microsoft Visual C++ 2015–2022 Redistributable (x64)](https://aka.ms/vs/17/release/vc_redist.x64.exe) (required by PaddlePaddle and OpenCV on Windows).

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/nickob4by/PDF-Renamer.git
cd PDF-Renamer
```

### 2. Create and Activate a Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Running the Web Application

Start the local server using Uvicorn:
```bash
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Once started, open your web browser and navigate to:
```
http://localhost:8000
```

---

## How to Use

1. **Step 1 — Input Receipts**:
   - Drag and drop your receipt PDF(s) into the upload area, or click **browse**.
   - Supports both single-page receipts and combined multi-page scanned batches (e.g. `June 2026.pdf`).

2. **Step 2 — Data Files (Master Excel & Billing Periods)**:
   - **Master Excel**: Displays the active master list and record count. Click **Replace master.xlsx** to upload a new IEMOP Collection Report (requires sheet `FOR OR` with columns `STL ID`, `NAME`, `BILLING NUMBER`, `NET`).
   - **Billing Periods**: Maps billing numbers to billing cycle codes (e.g. `0057514` -> `0526`). Click **Replace periods.txt** to update mappings.

3. **Step 3 — Output Destination**:
   - Enter your target destination folder, or click **📁 Browse...** to launch the native Windows folder explorer.
   - Quick preset shortcuts are provided for **Network Share** (`\\10.0.0.9\Accounting\Nicko\OR Renamer\Output`), **Project Output**, and **Desktop**.

4. **Step 4 — Start Renaming**:
   - Click **▶ Start Renaming** to begin processing.
   - Optional: Check **Dry run (preview only)** to simulate renaming without creating or moving files.
   - Watch live page-by-page OCR extraction, matched company names, confidence percentages, and file statuses.
   - When finished, access the output folder directly or click **📦 Download Renamed Files (ZIP)**.

---

## Project Structure

```
PDF-Renamer/
├── app.py                  # FastAPI web server and WebSocket orchestration
├── pipeline.py             # Shared batch processing and execution coordinator
├── splitter.py             # Multi-page PDF page separator
├── ocr.py                  # PaddleOCR image extraction engine
├── cropper.py              # Receipt region cropping & variant generator
├── extractor.py            # OCR word-level parsing, company and amount extractor
├── matcher.py              # RapidFuzz company and amount matching logic
├── billing_period.py       # Billing period file parser and resolver
├── renamer.py              # File path construction and rename executor
├── config.py               # Application configuration and directory paths
├── master.xlsx             # Default master Excel spreadsheet template
├── billing_periods.txt     # Default billing periods mapping file
├── templates/
│   └── index.html          # Web application user interface
├── static/
│   ├── app.js              # Frontend WebSocket and UI controller
│   └── style.css           # Modern dark-mode UI stylesheet
├── tests/                  # Automated pytest test suites
│   ├── test_loaders.py
│   ├── test_matcher.py
│   ├── test_extractor.py
│   ├── test_page_verdict.py
│   └── test_web_app.py
├── requirements.txt        # Pinned Python package dependencies
└── README.md               # Project documentation
```

---

## Running Automated Tests

Run the complete test suite with `pytest`:
```bash
pytest -v
```

All 36 tests cover loader parsing, company name normalization, dash stripping, rotated and upside-down receipt scanning, verdict decisions, and FastAPI endpoints.
