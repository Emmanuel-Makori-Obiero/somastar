import io

from app.core.errors import api_error  # noqa: F401
from app.integrations.llm import factory
from app.integrations.llm.base import LLMError
from app.integrations.storage.local import LocalStorage

PDF = b"%PDF-1.4\n%fake but has the right magic bytes\n"


def test_upload_returns_202_then_completes(client, auth, upload):
    r = upload()
    assert r.status_code == 202
    exam_id = r.json()["id"]

    detail = client.get(f"/api/exams/{exam_id}", headers=auth).json()  # background task ran
    assert detail["status"] == "completed"
    assert len(detail["questions"]) == 3
    assert [q["question_number"] for q in detail["questions"]] == ["1", "2", "3"]  # paper order kept
    assert detail["analysis"]["percentage_score"] == round((9 + 3 + 8) / 30 * 100, 1)


def test_unscored_questions_do_not_drag_percentage_down(client, auth, upload):
    r = upload(text="Q1 | A | 10 | 10\nQ2 | B | 10 |")
    detail = client.get(f"/api/exams/{r.json()['id']}", headers=auth).json()
    assert detail["analysis"]["percentage_score"] == 100.0
    assert detail["questions"][1]["student_score"] is None  # never fabricated


def test_bad_breakdown_line_fails_cleanly_with_helpful_message(client, auth, upload):
    r = upload(text="Q1 | Algebra | ten | 9")
    detail = client.get(f"/api/exams/{r.json()['id']}", headers=auth).json()
    assert detail["status"] == "failed"
    assert "Q1 | Topic | max_marks | your_score" in detail["error_message"]


def test_nothing_to_analyse_rejected(client, auth):
    r = client.post("/api/exams", data={"title": "T", "subject_name": "S"}, headers=auth)
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "NOTHING_TO_ANALYSE"


def test_file_type_is_detected_by_content_not_name(client, auth):
    fake = client.post(
        "/api/exams", data={"title": "T", "subject_name": "S"}, headers=auth,
        files={"file": ("exam.pdf", io.BytesIO(b"just some text, not a pdf"), "application/pdf")},
    )
    assert fake.status_code == 415

    ok = client.post(
        "/api/exams", data={"title": "T", "subject_name": "S", "total_marks": "40"}, headers=auth,
        files={"file": ("../../evil name.pdf", io.BytesIO(PDF), "application/pdf")},
    )
    assert ok.status_code == 202
    ref = LocalStorage().root.joinpath(*[]).iterdir()
    names = [p.name for p in ref]
    assert names and all(n.endswith(".pdf") and ".." not in n and " " not in n for n in names)


def test_oversized_upload_rejected(client, auth, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "MAX_UPLOAD_MB", 0)
    r = client.post(
        "/api/exams", data={"title": "T", "subject_name": "S"}, headers=auth,
        files={"file": ("a.pdf", io.BytesIO(PDF), "application/pdf")},
    )
    assert r.status_code == 413


def test_provider_error_marks_failed_with_safe_message(client, auth, upload, monkeypatch):
    class Boom:
        def analyse_exam(self, *a, **k):
            raise LLMError("The AI service is unavailable right now. Please try again in a moment.")
    monkeypatch.setattr(factory, "get_llm_provider", lambda: Boom())
    detail = client.get(f"/api/exams/{upload().json()['id']}", headers=auth).json()
    assert detail["status"] == "failed"
    assert "unavailable" in detail["error_message"]


def test_unexpected_crash_never_leaks_internals_or_sticks(client, auth, upload, monkeypatch):
    class Crash:
        def analyse_exam(self, *a, **k):
            raise RuntimeError("secret connection string postgres://user:pw@host")
    monkeypatch.setattr(factory, "get_llm_provider", lambda: Crash())
    detail = client.get(f"/api/exams/{upload().json()['id']}", headers=auth).json()
    assert detail["status"] == "failed"
    assert "postgres" not in detail["error_message"]
    assert detail["error_message"] == "Analysis failed. Please try again."


def test_reanalyze_is_idempotent_and_recovers_failed_exam(client, auth, upload, monkeypatch):
    exam_id = upload().json()["id"]
    first = client.get(f"/api/exams/{exam_id}", headers=auth).json()

    again = client.post(f"/api/exams/{exam_id}/reanalyze", headers=auth)
    assert again.status_code == 202
    second = client.get(f"/api/exams/{exam_id}", headers=auth).json()
    assert second["status"] == "completed"
    assert len(second["questions"]) == len(first["questions"])  # replaced, not duplicated
    skills = client.get("/api/assessment", headers=auth).json()["profile"]
    assert all(s["evidence_count"] == 1 for s in skills)


def test_exams_are_private_to_their_owner(client, auth, upload, make_user):
    exam_id = upload().json()["id"]
    other = make_user("other@example.com")
    assert client.get(f"/api/exams/{exam_id}", headers=other).status_code == 404
    assert client.delete(f"/api/exams/{exam_id}", headers=other).status_code == 404
    assert client.post(f"/api/exams/{exam_id}/reanalyze", headers=other).status_code == 404
    assert client.get("/api/exams", headers=other).json() == []


def test_delete_removes_everything_it_produced(client, auth, upload):
    exam_id = upload().json()["id"]
    assert client.get("/api/assessment", headers=auth).json()["exams_analysed"] == 1
    assert client.get("/api/revision", headers=auth).json()

    assert client.delete(f"/api/exams/{exam_id}", headers=auth).status_code == 204
    assert client.get(f"/api/exams/{exam_id}", headers=auth).status_code == 404
    a = client.get("/api/assessment", headers=auth).json()
    assert a["exams_analysed"] == 0 and a["profile"] == []
    assert client.get("/api/revision", headers=auth).json() == []


def test_list_pagination(client, auth, upload):
    for _ in range(3):
        upload()
    assert len(client.get("/api/exams?limit=2", headers=auth).json()) == 2
    assert len(client.get("/api/exams?limit=2&offset=2", headers=auth).json()) == 1
    assert client.get("/api/exams?limit=1000", headers=auth).status_code == 422
