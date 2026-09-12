import os
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://keyword-fit-engine.preview.emergentagent.com").rstrip("/")


def test_root_and_parse_text_file():
    root = requests.get(f"{BASE_URL}/api/", timeout=20)
    assert root.status_code == 200
    parsed = requests.post(
        f"{BASE_URL}/api/parse",
        files={"file": ("resume.txt", b"Jane Doe\njane@example.com\n\nSKILLS\nPython, React\n\nEXPERIENCE\nBuilt APIs")},
        timeout=20,
    )
    assert parsed.status_code == 200
    body = parsed.json()
    assert body["file_name"] == "resume.txt"
    assert "Python" in body["text"]
    assert body["sections"]["skills"] == "Python, React"


def test_analyze_history_analytics_and_exports():
    session = f"TEST_{uuid.uuid4()}"
    payload = {
        "session_id": session,
        "resume_text": "Jane Doe\njane@example.com\n\nSUMMARY\nProduct engineer.\n\nSKILLS\nPython React AWS\n\nEXPERIENCE\n• Led APIs and improved reliability by 20%\n• Built products for 4 teams\n\nEDUCATION\nB.S. Computer Science",
        "job_description": "Senior engineer building scalable Python React AWS APIs with PostgreSQL.",
        "file_name": "TEST_resume.txt",
    }
    analyzed = requests.post(f"{BASE_URL}/api/analyze", json=payload, timeout=120)
    assert analyzed.status_code == 200
    result = analyzed.json()
    assert result["session_id"] == session
    assert 0 <= result["scores"]["overall"] <= 100
    assert isinstance(result["ai"]["overview"], str)

    history = requests.get(f"{BASE_URL}/api/history/{session}", timeout=20)
    assert history.status_code == 200
    assert any(row["id"] == result["id"] for row in history.json())
    analytics = requests.get(f"{BASE_URL}/api/analytics/{session}", timeout=20)
    assert analytics.status_code == 200
    assert analytics.json()["trend"]

    for kind, content_type in (("docx", "wordprocessingml.document"), ("pdf", "application/pdf")):
        exported = requests.post(f"{BASE_URL}/api/export/{kind}", json={"text": result["ai"]["optimized_resume"]}, timeout=30)
        assert exported.status_code == 200
        assert content_type in exported.headers.get("content-type", "")
        assert len(exported.content) > 100