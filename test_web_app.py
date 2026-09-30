"""
test_web_app.py
Automated test suite for the FastAPI Web Service.
"""

import sys
from pathlib import Path
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app import app

client = TestClient(app)


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "PDF Auto Rename" in response.text
    assert "DASURECO" in response.text


def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["is_running"] is False
    assert data["master_records"] > 0


def test_upload_pdfs():
    sample_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF\n"
    response = client.post(
        "/api/upload-pdfs",
        files=[("files", ("test_receipt.pdf", sample_pdf_bytes, "application/pdf"))]
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uploaded"] == 1
    assert "test_receipt.pdf" in data["files"]


def test_download_results():
    response = client.get("/api/download-results")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"


def test_upload_master_and_periods():
    from app import job_mgr, UPLOAD_DIR
    import shutil
    orig_master = job_mgr.active_master_path
    orig_master_name = job_mgr.active_master_name
    orig_periods = job_mgr.active_periods_path
    orig_periods_name = job_mgr.active_periods_name

    active_m_file = UPLOAD_DIR / "active_master.xlsx"
    active_p_file = UPLOAD_DIR / "active_periods.txt"
    backup_m = UPLOAD_DIR / "active_master.xlsx.bak"
    backup_p = UPLOAD_DIR / "active_periods.txt.bak"

    if active_m_file.exists():
        shutil.copy2(active_m_file, backup_m)
    if active_p_file.exists():
        shutil.copy2(active_p_file, backup_p)

    try:
        # Test uploading periods file
        periods_content = b"SI_DASURECO__0055978_0426_2026\n"
        res_p = client.post(
            "/api/upload-periods",
            files=[("file", ("test_periods.txt", periods_content, "text/plain"))]
        )
        assert res_p.status_code == 200
        assert res_p.json()["count"] >= 1

        # Test uploading master file
        import io, openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "FOR OR"
        ws.append(["STL ID", "NAME", "BILLING NUMBER", "NET"])
        ws.append(["1590EC", "1590 ENERGY CORPORATION", "TS-WF-238F-0055978S", -1888.44])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)

        res_m = client.post(
            "/api/upload-master",
            files=[("file", ("test_master.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
        )
        assert res_m.status_code == 200
        assert res_m.json()["records"] == 1
    finally:
        if backup_m.exists():
            shutil.copy2(backup_m, active_m_file)
            backup_m.unlink(missing_ok=True)
        if backup_p.exists():
            shutil.copy2(backup_p, active_p_file)
            backup_p.unlink(missing_ok=True)

        job_mgr.active_master_path = orig_master
        job_mgr.active_master_name = orig_master_name
        job_mgr.active_periods_path = orig_periods
        job_mgr.active_periods_name = orig_periods_name
        job_mgr.save_state()


def test_cancel_when_idle():
    response = client.post("/api/cancel")
    assert response.status_code == 200
    assert "No job currently running" in response.json()["message"]


def test_start_with_custom_output_dir(tmp_path=None):
    from config import TEMP_DIR
    import tempfile
    custom_out = Path(tempfile.mkdtemp(prefix="test_custom_out_"))

    # Upload a dummy PDF so we have a file to start
    sample_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\nxref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n102\n%%EOF\n"
    client.post(
        "/api/upload-pdfs",
        files=[("files", ("dummy_for_start.pdf", sample_pdf_bytes, "application/pdf"))]
    )

    response = client.post(
        "/api/start",
        json={
            "source": "upload",
            "dry_run": True,
            "output_dir": str(custom_out),
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"
    assert data["output_dir"] == str(custom_out)
    assert custom_out.exists()
    assert (custom_out / "Failed").exists()


def test_browse_folders():
    res = client.get("/api/browse-folders")
    assert res.status_code == 200
    data = res.json()
    assert "current" in data
    assert "drives" in data
    assert "folders" in data
    assert isinstance(data["folders"], list)
    assert len(data["drives"]) > 0


def test_create_folder():
    import tempfile
    parent = Path(tempfile.mkdtemp(prefix="test_parent_"))
    res = client.post(
        "/api/create-folder",
        json={"parent": str(parent), "folder_name": "NewSubfolder"}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["error"] is False
    created_path = Path(data["created"])
    assert created_path.exists()
    assert created_path.name == "NewSubfolder"


def test_browse_native():
    import app as app_module
    old_func = app_module.open_native_folder_dialog
    try:
        app_module.open_native_folder_dialog = lambda current_path="": "D:\\Test\\SelectedFolder"
        res = client.post("/api/browse-native", json={"current_path": ""})
        assert res.status_code == 200
        data = res.json()
        assert data["path"] == "D:\\Test\\SelectedFolder"
        assert data["cancelled"] is False
    finally:
        app_module.open_native_folder_dialog = old_func


def main():
    tests = [
        test_index_page,
        test_api_status,
        test_upload_pdfs,
        test_download_results,
        test_upload_master_and_periods,
        test_cancel_when_idle,
        test_start_with_custom_output_dir,
        test_browse_folders,
        test_create_folder,
        test_browse_native,
    ]




    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL  {test.__name__}: {e}")

    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()

