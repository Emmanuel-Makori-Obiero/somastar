def test_skill_names_are_normalised_and_merged(client, auth, upload):
    upload(text="Q1 | A | 10 | 10 | Graph reading\nQ2 | B | 10 | 0 | graph   reading")
    profile = client.get("/api/assessment", headers=auth).json()["profile"]
    assert [p["skill"] for p in profile] == ["Graph reading"]
    assert profile[0]["evidence_count"] == 2
    assert profile[0]["average_score"] == 50.0


def test_strengths_weaknesses_and_careers(client, auth, upload):
    upload(text="Q1 | A | 10 | 10 | mathematical reasoning\nQ2 | B | 10 | 1 | Written explanation")
    a = client.get("/api/assessment", headers=auth).json()
    assert [s["skill"] for s in a["strengths"]] == ["Mathematical reasoning"]
    assert [w["skill"] for w in a["weaknesses"]] == ["Written explanation"]
    assert "Engineering" in a["career_suggestions"]  # matched case-insensitively


def test_revision_items_created_for_weak_questions_only(client, auth, upload):
    upload(text="Q1 | Algebra | 10 | 10\nQ2 | Geometry | 10 | 2\nQ3 | Optics | 10 | 5")
    items = client.get("/api/revision", headers=auth).json()
    assert [i["topic"] for i in items].count("Algebra") == 0
    assert {i["topic"] for i in items} == {"Geometry", "Optics"}
    assert all(i["status"] == "pending" and i["exam_title"] == "Mid-Term" for i in items)


def test_revision_status_update_and_ownership(client, auth, upload, make_user):
    upload(text="Q1 | Geometry | 10 | 2")
    item = client.get("/api/revision", headers=auth).json()[0]

    r = client.patch(f"/api/revision/{item['id']}", json={"status": "reviewed"}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "reviewed" and r.json()["next_review_at"]
    assert client.patch(f"/api/revision/{item['id']}", json={"status": "bogus"}, headers=auth).status_code == 422

    other = make_user("other@example.com")
    assert client.patch(f"/api/revision/{item['id']}", json={"status": "mastered"}, headers=other).status_code == 404
    assert len(client.get("/api/revision?status=reviewed", headers=auth).json()) == 1


def test_chat_persists_history_and_survives_provider_failure(client, auth, monkeypatch):
    from app.integrations.llm import factory
    from app.integrations.llm.base import LLMError

    ok = client.post("/api/assessment/chat", json={"message": "What next?"}, headers=auth)
    assert ok.status_code == 200 and ok.json()["role"] == "assistant"

    class Down:
        def chat(self, *a, **k):
            raise LLMError("The AI service is unavailable right now. Please try again in a moment.")
    monkeypatch.setattr(factory, "get_llm_provider", lambda: Down())
    bad = client.post("/api/assessment/chat", json={"message": "Hello?"}, headers=auth)
    assert bad.status_code == 503
