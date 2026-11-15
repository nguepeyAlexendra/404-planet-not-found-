import pytest


def _levels(client, h=None):
    return client.get("/api/v1/learning/levels", headers=h or {}).json()


def _answers(client, level_id, correct=True):
    from app.core.db import SessionLocal
    from app.models import AnswerOption, Question, Quiz
    db = SessionLocal()
    try:
        quiz = db.query(Quiz).filter(Quiz.level_id == level_id).one()
        out = {}
        for q in quiz.questions:
            good = next(o.id for o in q.options if o.is_correct)
            wrong = next(o.id for o in q.options if not o.is_correct)
            out[str(q.id)] = good if correct else wrong
        return quiz.id, out
    finally:
        db.close()


def test_stories_catalogue_and_detail_are_labelled_as_examples(client):
    lst = client.get("/api/v1/stories").json()
    assert {s["slug"] for s in lst} == {"amazonie-exemple", "demo-defrichement"} and all(s["is_example"] for s in lst)
    s = client.get("/api/v1/stories/demo-defrichement").json()
    assert len(s["scenes"]) == 4 and [x["order"] for x in s["scenes"]] == [1, 2, 3, 4]
    assert all(sc["provenance"] and sc["limits"] for sc in s["scenes"]) and s["sources"]
    assert s["scenes"][2]["date_start"] < s["scenes"][2]["date_end"] and "nisar-gcov-hv" in s["scenes"][2]["layers"]
    assert client.get(f"/api/v1/stories/{s['id']}").json()["slug"] == "demo-defrichement"  # accès par id
    assert client.get("/api/v1/stories/inconnue").status_code == 404
    amazon = client.get("/api/v1/stories/amazonie-exemple").json()
    assert all(sc["layers"] == [] for sc in amazon["scenes"])  # aucune donnée associée : pas de fausse couche


def test_levels_lock_rules(client, cid, h):
    lv = _levels(client, h)
    assert [l["unlocked"] for l in lv] == [True, False, False, False, False] and [l["xp"] for l in lv] == [100, 200, 300, 400, 500]
    assert client.get(f"/api/v1/learning/levels/{lv[0]['id']}", headers=h).status_code == 200
    locked = client.get(f"/api/v1/learning/levels/{lv[2]['id']}", headers=h)
    assert locked.status_code == 403 and locked.json()["error"]["code"] == "level_locked"
    quiz_id, ans = _answers(client, lv[1]["id"])
    assert client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": ans}, headers=h).status_code == 403


def test_level_detail_never_leaks_answers(client, h):
    lv = _levels(client, h)[0]
    d = client.get(f"/api/v1/learning/levels/{lv['id']}", headers=h).json()
    assert d["lessons"] and len(d["quiz"]["questions"]) == 4
    assert "is_correct" not in str(d) and "explanation" not in str(d)


def test_attempt_scoring_xp_badge_once_and_progression(client, h):
    lv = _levels(client, h)
    quiz_id, good = _answers(client, lv[0]["id"], True)
    _, bad = _answers(client, lv[0]["id"], False)
    fail = client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": bad}, headers=h).json()
    assert fail["passed"] is False and fail["xp_awarded"] == 0 and fail["score"] == 0 and fail["new_badge"] is None
    assert all(r["explanation"] for r in fail["results"])
    ok = client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": good}, headers=h).json()
    assert ok["passed"] and ok["score"] == 1 and ok["xp_awarded"] == 100 and ok["new_badge"] == "explorateur-radar"
    again = client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": good}, headers=h).json()
    assert again["passed"] and again["xp_awarded"] == 0 and again["new_badge"] is None  # pas de double récompense
    prog = client.get("/api/v1/learning/progress", headers=h).json()
    assert prog["xp"] == 100 and prog["completed_levels"] == [1] and len(prog["badges"]) == 1 and not prog["certificate_eligible"]
    assert _levels(client, h)[1]["unlocked"] is True  # le niveau 2 s'ouvre
    assert [b["key"] for b in client.get("/api/v1/learning/badges", headers=h).json()] == ["explorateur-radar"]


def test_progress_is_isolated_between_sessions(client, h):
    lv = _levels(client, h)
    quiz_id, good = _answers(client, lv[0]["id"])
    client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": good}, headers=h)
    other = client.get("/api/v1/learning/progress", headers={"X-Client-Id": "autre-session-xyz"}).json()
    assert other["xp"] == 0 and other["completed_levels"] == []


def test_attempt_validation(client, h):
    lv = _levels(client, h)[0]
    quiz_id, good = _answers(client, lv["id"])
    partial = dict(list(good.items())[:2])
    assert client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": partial}, headers=h).status_code == 400
    wrong_opt = {**good, next(iter(good)): 999999}
    assert client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": wrong_opt}, headers=h).json()["error"]["code"] == "invalid_answers"
    assert client.post("/api/v1/learning/quiz/999999/attempts", json={"answers": good}, headers=h).status_code == 404
    assert client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": {"a": 1}}, headers=h).status_code == 422
    assert client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": good}).status_code == 400  # X-Client-Id requis


def test_certificate_only_after_five_levels_then_verification(client, h):
    assert client.post("/api/v1/learning/certificate", json={"name": "Awa Ngono"}, headers=h).status_code == 403
    for lv in _levels(client, h):
        quiz_id, good = _answers(client, lv["id"])
        r = client.post(f"/api/v1/learning/quiz/{quiz_id}/attempts", json={"answers": good}, headers=h).json()
        assert r["passed"]
    prog = client.get("/api/v1/learning/progress", headers=h).json()
    assert prog["xp"] == 1500 and len(prog["badges"]) == 5 and prog["certificate_eligible"]
    assert client.post("/api/v1/learning/certificate", json={"name": "A"}, headers=h).status_code == 422
    c = client.post("/api/v1/learning/certificate", json={"name": "Awa Ngono"}, headers=h)
    assert c.status_code == 201
    code = c.json()["code"]
    assert client.post("/api/v1/learning/certificate", json={"name": "Awa Ngono"}, headers=h).status_code == 409
    v = client.get(f"/api/v1/learning/certificate/{code}").json()
    assert v["valid"] and v["holder"] == "Awa N." and "Ngono" not in str(v)  # nom partiellement masqué
    assert client.get(f"/api/v1/learning/certificate/{code}/pdf").content[:5] == b"%PDF-"
    assert client.get("/api/v1/learning/certificate/INCONNU").status_code == 404


def test_glossary_size_search_and_level_filter(client):
    all_terms = client.get("/api/v1/learning/glossary").json()
    assert len(all_terms) >= 50 and all(t["definition"] for t in all_terms)
    found = [t["term"] for t in client.get("/api/v1/learning/glossary", params={"q": "speckle"}).json()]
    assert any(t.startswith("Speckle") for t in found) and len(found) < len(all_terms)  # recherche aussi dans les définitions
    assert all(t["level"] == 5 for t in client.get("/api/v1/learning/glossary", params={"level": 5}).json())
    assert client.get("/api/v1/learning/glossary", params={"level": 9}).status_code == 422


def test_invalid_client_id_formats(client):
    for bad in ("court", "a" * 65, "avec espace 123456", "<script>12345"):
        assert client.get("/api/v1/learning/progress", headers={"X-Client-Id": bad}).status_code == 400
