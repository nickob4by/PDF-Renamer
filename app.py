"""
app.py
Dedicated FastAPI Web Service for PDF Auto Rename.
Replaces the desktop GUI and CLI with a fast, zero-install, server-hosted web app.
"""

import asyncio
import io
import os
import shutil
import json
import threading
import time
import zipfile
from pathlib import Path
from typing import Optional, Set

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import (
    BASE_DIR,
    FAILED_DIR,
    INPUT_DIR,
    LOG_DIR,
    OUTPUT_DIR,
    TEMP_DIR,
    UNKNOWN_DIR,
)
from billing_period import load_billing_periods
from matcher import ReceiptMatcher
from pipeline import process_pdfs

# ---------------------------------------------------------------------------
# FastAPI App Initialization
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PDF Auto Rename Web Service",
    description="Automated OCR invoice renaming for DASURECO",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = BASE_DIR / "config_state.json"


# ---------------------------------------------------------------------------
# Global Job & WebSocket State
# ---------------------------------------------------------------------------
class JobManager:
    def __init__(self):
        self.is_running = False
        self.cancel_flag = threading.Event()
        self.current_task = None
        self.active_websockets: Set[WebSocket] = set()
        self.event_loop = None
        self.last_results = []
        self.last_run_summary = {}

        # Default paths
        self.active_master_path = BASE_DIR / "master.xlsx"
        self.active_master_name = "master.xlsx"
        self.active_periods_path = BASE_DIR / "billing_periods.txt"
        self.active_periods_name = "billing_periods.txt"
        self.last_output_dir = OUTPUT_DIR

        # If a dedicated active master already exists in uploads, prioritize it
        active_master = UPLOAD_DIR / "active_master.xlsx"
        if active_master.exists():
            self.active_master_path = active_master
            self.active_master_name = "active_master.xlsx"

        active_periods = UPLOAD_DIR / "active_periods.txt"
        if active_periods.exists():
            self.active_periods_path = active_periods
            self.active_periods_name = "active_periods.txt"

        self.load_state()

    def load_state(self):
        if STATE_FILE.exists():
            try:
                data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
                master_p = Path(data.get("active_master_path", ""))
                if master_p.exists():
                    self.active_master_path = master_p
                    self.active_master_name = data.get("active_master_name", master_p.name)

                periods_p = Path(data.get("active_periods_path", ""))
                if periods_p.exists():
                    self.active_periods_path = periods_p
                    self.active_periods_name = data.get("active_periods_name", periods_p.name)

                out_p = data.get("last_output_dir", "")
                if out_p:
                    self.last_output_dir = Path(out_p)
            except Exception as e:
                print(f"Error loading state: {e}")

    def save_state(self):
        try:
            data = {
                "active_master_path": str(self.active_master_path),
                "active_master_name": self.active_master_name,
                "active_periods_path": str(self.active_periods_path),
                "active_periods_name": self.active_periods_name,
                "last_output_dir": str(self.last_output_dir),
            }
            STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"Error saving state: {e}")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_websockets.discard(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_websockets.discard(ws)

    def emit_sync(self, message: dict):
        """Thread-safe event broadcast to WebSocket clients."""
        if self.event_loop and self.event_loop.is_running():
            asyncio.run_coroutine_threadsafe(self.broadcast(message), self.event_loop)


job_mgr = JobManager()


@app.on_event("startup")
async def startup_event():
    job_mgr.event_loop = asyncio.get_running_loop()


# ---------------------------------------------------------------------------
# Web UI Entrypoint
# ---------------------------------------------------------------------------
@app.get("/")
async def serve_index():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return JSONResponse({"error": "templates/index.html not found"}, status_code=404)
    return FileResponse(index_file)


# ---------------------------------------------------------------------------
# REST API Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    """Return current server status, record counts, and paths."""
    excel_records = 0
    sample_billing = ""
    try:
        matcher = ReceiptMatcher(excel_path=job_mgr.active_master_path)
        excel_records = len(matcher.records)
        if matcher.records:
            sample_billing = matcher.records[0].get("billing_number", "")
    except Exception:
        pass

    periods_count = 0
    try:
        periods = load_billing_periods(job_mgr.active_periods_path)
        periods_count = len(periods)
    except Exception:
        pass

    uploaded_pdfs = []
    if UPLOAD_DIR.exists():
        uploaded_pdfs = sorted([p.name for p in UPLOAD_DIR.glob("*.pdf")])

    return {
        "status": "online",
        "is_running": job_mgr.is_running,
        "input_dir": str(INPUT_DIR),
        "output_dir": str(job_mgr.last_output_dir or OUTPUT_DIR),
        "failed_dir": str(FAILED_DIR),
        "unknown_dir": str(UNKNOWN_DIR),
        "master_records": excel_records,
        "master_billing": sample_billing,
        "active_clients": len(job_mgr.active_websockets),
        "active_master": job_mgr.active_master_name or str(job_mgr.active_master_path.name),
        "active_periods": job_mgr.active_periods_name or str(job_mgr.active_periods_path.name),
        "periods_count": periods_count,
        "uploaded_files": uploaded_pdfs,
    }


def open_native_folder_dialog(initial_dir: str = "") -> str:
    """Open Windows native Folder Browser Dialog using Python's Win32 Tkinter bridge."""
    import subprocess
    import sys

    init_dir = ""
    if initial_dir and os.path.exists(initial_dir):
        init_dir = os.path.normpath(initial_dir)

    script = (
        "import tkinter as tk\n"
        "from tkinter import filedialog\n"
        "import sys, os\n"
        "root = tk.Tk()\n"
        "root.withdraw()\n"
        "root.wm_attributes('-topmost', 1)\n"
        f"init_dir = {repr(init_dir)}\n"
        "path = filedialog.askdirectory(title='Select Output Destination Folder', initialdir=init_dir or None)\n"
        "root.destroy()\n"
        "if path:\n"
        "    sys.stdout.write(os.path.normpath(path))\n"
    )

    try:
        res = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=180,
        )
        return res.stdout.strip()
    except Exception as e:
        print(f"Error opening native folder dialog: {e}")
        return ""


class BrowseNativeRequest(BaseModel):
    current_path: Optional[str] = None


@app.post("/api/browse-native")
async def browse_native(req: BrowseNativeRequest):
    """Trigger the native Windows Explorer folder selection dialog."""
    chosen_path = await asyncio.to_thread(open_native_folder_dialog, req.current_path or "")
    if chosen_path:
        return {"path": chosen_path, "cancelled": False}
    return {"path": None, "cancelled": True}


def get_system_drives():
    drives = []
    if os.name == "nt":
        try:
            import ctypes
            import string
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if (bitmask >> (ord(letter) - ord("A"))) & 1:
                    drives.append(f"{letter}:\\")
        except Exception:
            drives = ["C:\\"]
    else:
        drives = ["/"]
    return drives


@app.get("/api/browse-folders")
async def browse_folders(path: Optional[str] = None):
    """List subfolders and drives for directory browsing modal."""
    drives = get_system_drives()
    presets = [
        {"name": "network", "label": "Network Share", "path": str(OUTPUT_DIR)},
        {"name": "local", "label": "Local Output", "path": str(BASE_DIR / "output")},
        {"name": "desktop", "label": "Desktop", "path": str(Path.home() / "Desktop")},
    ]

    if not path or not path.strip():
        if job_mgr.last_output_dir and job_mgr.last_output_dir.exists():
            target = job_mgr.last_output_dir
        elif OUTPUT_DIR.exists():
            target = OUTPUT_DIR
        else:
            target = BASE_DIR
    else:
        target = Path(path.strip())

    try:
        if not target.exists():
            if target.parent.exists():
                target = target.parent
            else:
                target = BASE_DIR
    except Exception:
        target = BASE_DIR

    folders = []
    try:
        for item in target.iterdir():
            try:
                if item.is_dir() and not item.name.startswith((".", "$")):
                    folders.append(item.name)
            except (PermissionError, OSError):
                continue
        folders.sort(key=str.lower)
    except (PermissionError, OSError):
        pass

    parent_path = None
    try:
        if target.parent and target.parent != target:
            parent_path = str(target.parent)
    except Exception:
        pass

    return {
        "current": str(target),
        "parent": parent_path,
        "drives": drives,
        "folders": folders,
        "presets": presets,
    }


class CreateFolderRequest(BaseModel):
    parent: str
    folder_name: str


@app.post("/api/create-folder")
async def create_folder(req: CreateFolderRequest):
    """Create a new folder inside parent directory."""
    name = req.folder_name.strip()
    if not name or any(c in name for c in r'\/:*?"<>|'):
        return JSONResponse({"error": True, "message": "Invalid folder name."}, status_code=400)

    parent = Path(req.parent.strip())
    new_dir = parent / name
    try:
        new_dir.mkdir(parents=True, exist_ok=True)
        return {"error": False, "created": str(new_dir)}
    except Exception as e:
        return JSONResponse({"error": True, "message": str(e)}, status_code=400)


@app.post("/api/scan-network")
async def scan_network():
    """Scan the configured network share input directory."""
    if not INPUT_DIR.exists():
        return {
            "error": True,
            "message": f"Network share path not found: {INPUT_DIR}",
            "files": [],
        }

    try:
        files = sorted(f.name for f in INPUT_DIR.glob("*.pdf"))
        return {
            "error": False,
            "path": str(INPUT_DIR),
            "files": files,
            "count": len(files),
        }
    except Exception as e:
        return {"error": True, "message": str(e), "files": []}


@app.post("/api/upload-pdfs")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """Accept multi-file PDF uploads and store in temp upload folder."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_files = []

    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        dest = UPLOAD_DIR / f.filename
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)
        saved_files.append(f.filename)

    return {"uploaded": len(saved_files), "files": saved_files}


class RemoveUploadRequest(BaseModel):
    filename: str


@app.post("/api/remove-upload")
async def remove_upload(req: RemoveUploadRequest):
    """Remove a specific uploaded PDF file from UPLOAD_DIR."""
    fname = Path(req.filename).name  # Prevent directory traversal
    target = UPLOAD_DIR / fname
    if target.is_file() and target.suffix.lower() == ".pdf":
        try:
            target.unlink()
            return {"removed": True, "filename": fname}
        except Exception as e:
            return JSONResponse({"error": f"Failed to delete {fname}: {str(e)}"}, status_code=500)
    return {"removed": False, "filename": fname, "message": "File not found"}


@app.post("/api/clear-uploads")
async def clear_uploads():
    """Purge all uploaded PDF files from UPLOAD_DIR while keeping master excel and periods txt."""
    deleted = []
    if UPLOAD_DIR.exists():
        for p in UPLOAD_DIR.glob("*.pdf"):
            try:
                p.unlink()
                deleted.append(p.name)
            except Exception as e:
                print(f"Error removing {p.name}: {e}")
    return {"cleared": len(deleted), "files": deleted}


@app.post("/api/upload-master")
async def upload_master(file: UploadFile = File(...)):
    """Upload a new master Excel file with Excel file-lock tolerance."""
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        return JSONResponse(
            {"error": True, "message": "Only .xlsx and .xls Excel files are supported."},
            status_code=400,
        )

    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        # Always write to a dedicated uploaded file first so open Excel instances don't block upload
        safe_name = f"master_uploaded_{int(time.time())}_{file.filename}"
        dest = UPLOAD_DIR / safe_name
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Validate by loading records through ReceiptMatcher
        matcher = ReceiptMatcher(excel_path=dest)
        if len(matcher.records) == 0:
            return JSONResponse(
                {
                    "error": True,
                    "message": "Uploaded Excel file has 0 valid records. Please verify the 'FOR OR' sheet and column headers (STL ID, NAME, BILLING NUMBER, NET).",
                },
                status_code=400,
            )

        # Save a dedicated active master copy that remains free from Windows locks
        active_copy = UPLOAD_DIR / "active_master.xlsx"
        try:
            shutil.copy2(dest, active_copy)
            job_mgr.active_master_path = active_copy
        except Exception:
            job_mgr.active_master_path = dest

        job_mgr.active_master_name = file.filename
        job_mgr.save_state()

        # Try to copy to default master.xlsx if not currently locked by Excel
        try:
            default_path = BASE_DIR / "master.xlsx"
            shutil.copy2(dest, default_path)
        except (PermissionError, OSError):
            pass

        sample_billing = matcher.records[0].get("billing_number", "") if matcher.records else ""

        return {
            "error": False,
            "message": "Master updated successfully",
            "records": len(matcher.records),
            "filename": file.filename,
            "billing": sample_billing,
        }

    except Exception as e:
        return JSONResponse(
            {"error": True, "message": f"Failed to parse Excel file: {str(e)}"},
            status_code=400,
        )


@app.post("/api/upload-periods")
async def upload_periods(file: UploadFile = File(...)):
    """Upload a new billing periods text file with file-lock tolerance."""
    if not file.filename.lower().endswith(".txt"):
        return JSONResponse(
            {"error": True, "message": "Only .txt files are supported for billing periods."},
            status_code=400,
        )

    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = f"periods_uploaded_{int(time.time())}_{file.filename}"
        dest = UPLOAD_DIR / safe_name
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        periods = load_billing_periods(dest)
        if len(periods) == 0:
            return JSONResponse(
                {
                    "error": True,
                    "message": "Uploaded text file contains 0 valid billing period mappings.",
                },
                status_code=400,
            )

        active_periods = UPLOAD_DIR / "active_periods.txt"
        try:
            shutil.copy2(dest, active_periods)
            job_mgr.active_periods_path = active_periods
        except Exception:
            job_mgr.active_periods_path = dest

        job_mgr.active_periods_name = file.filename
        job_mgr.save_state()

        try:
            default_path = BASE_DIR / "billing_periods.txt"
            shutil.copy2(dest, default_path)
        except (PermissionError, OSError):
            pass

        return {
            "error": False,
            "message": "Billing periods updated successfully",
            "count": len(periods),
            "filename": file.filename,
        }

    except Exception as e:
        return JSONResponse(
            {"error": True, "message": f"Failed to parse periods file: {str(e)}"},
            status_code=400,
        )


class StartJobRequest(BaseModel):
    source: str = "upload"  # "upload"
    dry_run: bool = False
    output_dir: Optional[str] = None
    files: Optional[list[str]] = None


@app.post("/api/start")
async def start_job(req: StartJobRequest):
    """Start batch processing in background."""
    if job_mgr.is_running:
        return JSONResponse({"error": "A batch job is already running."}, status_code=400)

    # Determine target output folder
    if req.output_dir and req.output_dir.strip():
        target_output_dir = Path(req.output_dir.strip())
    else:
        target_output_dir = OUTPUT_DIR

    target_failed_dir = target_output_dir / "Failed"

    try:
        target_output_dir.mkdir(parents=True, exist_ok=True)
        target_failed_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return JSONResponse(
            {"error": f"Cannot create or access target output directory '{target_output_dir}': {str(e)}"},
            status_code=400,
        )

    job_mgr.last_output_dir = target_output_dir

    # Determine input PDF files
    if req.source == "upload":
        if req.files:
            # Use strictly the user-specified files that exist in UPLOAD_DIR
            pdf_files = []
            for fname in req.files:
                safe_name = Path(fname).name
                p = UPLOAD_DIR / safe_name
                if p.is_file() and p.suffix.lower() == ".pdf":
                    pdf_files.append(p)
        else:
            pdf_files = sorted(UPLOAD_DIR.glob("*.pdf"))
    else:
        if not INPUT_DIR.exists():
            return JSONResponse(
                {"error": f"Network Input directory not found: {INPUT_DIR}"}, status_code=400
            )
        pdf_files = sorted(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        return JSONResponse(
            {"error": f"No PDF files found for source '{req.source}'."}, status_code=400
        )

    job_mgr.is_running = True
    job_mgr.cancel_flag.clear()
    job_mgr.last_results = []

    def run_worker():
        try:
            job_mgr.emit_sync({"phase": "startup", "message": "Initializing pipeline..."})

            def on_progress(event):
                # Format error to string if present
                if event.get("error"):
                    event["error_str"] = str(event["error"])
                    event["error"] = None
                if event.get("saved_as") and not req.dry_run:
                    job_mgr.last_results.append(event["saved_as"])
                job_mgr.emit_sync(event)

            res = process_pdfs(
                pdf_files,
                output_dir=target_output_dir,
                failed_dir=target_failed_dir,
                dry_run=req.dry_run,
                master_file=job_mgr.active_master_path,
                billing_periods_file=job_mgr.active_periods_path,
                on_progress=on_progress,
                should_cancel=job_mgr.cancel_flag.is_set,
            )


            job_mgr.last_run_summary = res
            phase = "cancelled" if res["cancelled"] else "complete"
            job_mgr.emit_sync({
                "phase": phase,
                "cancelled": res["cancelled"],
                "success": res["success"],
                "failed": res["failed"],
                "unknown": res["unknown"],
                "total": res["total_pages"],
                "dry_run": req.dry_run,
            })

        except Exception as e:
            job_mgr.emit_sync({"phase": "error", "message": str(e)})
        finally:
            job_mgr.is_running = False

    thread = threading.Thread(target=run_worker, daemon=True)
    thread.start()

    return {
        "status": "started",
        "file_count": len(pdf_files),
        "dry_run": req.dry_run,
        "output_dir": str(target_output_dir),
    }


@app.post("/api/cancel")
async def cancel_job():
    """Cancel the current running job."""
    if not job_mgr.is_running:
        return {"message": "No job currently running."}

    job_mgr.cancel_flag.set()
    job_mgr.emit_sync({"phase": "warn", "message": "Cancellation requested..."})
    return {"message": "Cancellation signal sent."}


@app.get("/api/download-results")
async def download_results():
    """Package output directory into a ZIP archive for client download."""
    zip_buffer = io.BytesIO()
    
    # Safely select directory with local fallback if UNC path is unreachable
    out_dir = job_mgr.last_output_dir
    try:
        if not out_dir or not out_dir.exists():
            out_dir = OUTPUT_DIR
            if not out_dir.exists():
                out_dir = BASE_DIR / "output"
    except (OSError, Exception):
        out_dir = BASE_DIR / "output"

    unknown_dir = out_dir / "Unknown Billing Period"
    failed_dir = out_dir / "Failed"

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for folder in (out_dir, unknown_dir, failed_dir):
            try:
                if folder.exists():
                    for item in folder.glob("*.pdf"):
                        arcname = os.path.relpath(item, out_dir)
                        zip_file.write(item, arcname=arcname)
            except (OSError, Exception) as e:
                print(f"Skipping folder {folder} during zip packaging: {e}")

    zip_buffer.seek(0)
    filename = f"Renamed_Invoices_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )



# ---------------------------------------------------------------------------
# WebSocket Channel
# ---------------------------------------------------------------------------
@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await job_mgr.connect(websocket)
    try:
        # Immediately send current state on connect
        await websocket.send_json({
            "phase": "status",
            "is_running": job_mgr.is_running,
            "last_summary": job_mgr.last_run_summary,
        })
        while True:
            # Keep connection open / listen for heartbeat
            await websocket.receive_text()
    except WebSocketDisconnect:
        job_mgr.disconnect(websocket)
    except Exception:
        job_mgr.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print(" PDF Auto Rename — FastAPI Web Server")
    print(" Listening on http://0.0.0.0:8000")
    print("=" * 60)
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
