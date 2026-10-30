import json
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core_backend.core.dependencies import get_current_user
from app.core_backend.database.supabase_db import DatabaseManager

client = TestClient(app)

TEST_STUDENT_ID = "student_eval_test_user_001"
AUTH_USER = {"id": TEST_STUDENT_ID, "email": "student@neurolab.ai", "role": "authenticated"}
AUTH_HEADERS = {"Authorization": "Bearer test_token_p11"}


@pytest.fixture(autouse=True)
def setup_auth_and_db():
    async def override_user(authorization=None):
        return AUTH_USER

    app.dependency_overrides[get_current_user] = override_user
    db = DatabaseManager()
    with db._read_local.__globals__["db_lock"]:
        data = db._read_local()
        # Reset user's XP and mastery records
        if "xp" in data:
            data["xp"][TEST_STUDENT_ID] = 0
        if "mastery_records" in data:
            data["mastery_records"] = {
                k: v for k, v in data["mastery_records"].items()
                if not k.startswith(f"{TEST_STUDENT_ID}:")
            }
        if "xp_ledger" in data:
            data["xp_ledger"] = {
                k: v for k, v in data["xp_ledger"].items()
                if not k.startswith(f"{TEST_STUDENT_ID}:") and v.get("user_id") != TEST_STUDENT_ID
            }
        db._write_local(data)

    yield

    app.dependency_overrides.clear()


def parse_sse_events(response_text: str):
    events = []
    for line in response_text.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    return events


def test_adversarial_trigger_phrase_rejected():
    """
    Verification: Student sends trivial trigger phrase 'it goes up' without physical reasoning.
    Must be rejected with guidance, 0 XP awarded, and state NOT set to mastery_confirmed.
    """
    payload = {
        "concept": "Newton's 3rd Law",
        "question": "If a rocket pushes exhaust downward, what happens to the rocket?",
        "answer": "it goes up",
    }
    response = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["is_correct"] is False
    assert res_data["mastery_awarded"] is False
    assert res_data["xp_awarded"] == 0
    assert res_data["state"] == "answer_evaluated"
    assert "mechanism" in res_data["explanation"].lower() or "forces" in res_data["explanation"].lower()


def test_adversarial_negation_rejected():
    """
    Verification: Student sends direct negation like 'it does not go up'.
    Must be rejected with 0 XP awarded.
    """
    payload = {
        "concept": "Newton's 3rd Law",
        "question": "If a rocket pushes exhaust downward, what happens to the rocket?",
        "answer": "It does not go up and remains stationary.",
    }
    response = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["is_correct"] is False
    assert res_data["mastery_awarded"] is False
    assert res_data["xp_awarded"] == 0
    assert res_data["state"] == "answer_evaluated"


def test_adversarial_bogus_explanation_rejected():
    """
    Verification: Student attempts prompt gaming with bogus explanation ('aliens').
    Must be rejected with 0 XP awarded.
    """
    payload = {
        "concept": "Newton's 3rd Law",
        "question": "If a rocket pushes exhaust downward, what happens to the rocket?",
        "answer": "it goes up because aliens push it with magic force",
    }
    response = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["is_correct"] is False
    assert res_data["mastery_awarded"] is False
    assert res_data["xp_awarded"] == 0


def test_valid_conceptual_understanding_awards_mastery():
    """
    Verification: Student provides genuine physical reasoning connecting downward action
    to equal and opposite upward reaction force.
    Mastery must be confirmed and 100 XP awarded.
    """
    payload = {
        "concept": "Newton's 3rd Law",
        "question": "If a rocket pushes exhaust downward, what happens to the rocket?",
        "answer": "The downward expulsion of exhaust gas produces an equal and opposite upward reaction force on the rocket, accelerating it upward.",
    }
    response = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["is_correct"] is True
    assert res_data["confidence"] >= 0.80
    assert res_data["state"] == "mastery_confirmed"
    assert res_data["mastery_awarded"] is True
    assert res_data["xp_awarded"] == 100

    # Verify XP reflected in DB
    db = DatabaseManager()
    total_xp = db.get_user_xp(TEST_STUDENT_ID)
    assert total_xp == 100


def test_mastery_xp_award_is_strictly_idempotent():
    """
    Verification: Submitting the same mastery answer twice or retrying over the network
    must NOT award duplicate XP. Second call must return xp_awarded=0 and mastery_awarded=False.
    """
    payload = {
        "concept": "Newton's 3rd Law",
        "question": "If a rocket pushes exhaust downward, what happens to the rocket?",
        "answer": "By Newton's third law, the downward force on gas creates an equal and opposite upward reaction force on the rocket.",
    }

    # First submission -> Awards 100 XP
    resp1 = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert resp1.status_code == 200
    assert resp1.json()["mastery_awarded"] is True
    assert resp1.json()["xp_awarded"] == 100

    # Second submission (network retry / duplicate) -> 0 duplicate XP awarded
    resp2 = client.post("/api/tutor/evaluate-answer", json=payload, headers=AUTH_HEADERS)
    assert resp2.status_code == 200
    assert resp2.json()["mastery_awarded"] is False
    assert resp2.json()["xp_awarded"] == 0
    assert resp2.json()["state"] == "mastery_confirmed"

    # Verify total DB XP is still exactly 100, not 200
    db = DatabaseManager()
    assert db.get_user_xp(TEST_STUDENT_ID) == 100


def test_chat_stream_does_not_give_free_xp_for_trigger_phrase(monkeypatch):
    """
    Verification: In the conversational chat stream, sending 'it goes up'
    no longer triggers canned demo responses or free XP.
    """
    from app.core_backend.routes import tutor as tutor_route

    mock_model = MagicMock()
    mock_chunk = MagicMock()
    mock_chunk.text = "Can you explain why the rocket moves upward according to Newton's laws?"
    mock_model.generate_content.return_value = [mock_chunk]
    monkeypatch.setattr(tutor_route.tutor_service, "model", mock_model)

    payload = {"prompt": "it goes up"}
    response = client.post("/api/tutor/chat/stream", json=payload, headers=AUTH_HEADERS)
    assert response.status_code == 200

    events = parse_sse_events(response.text)
    # Check that no kg_update or unearned XP event is emitted
    kg_updates = [e.get("kg_update") for e in events if "kg_update" in e]
    assert len(kg_updates) == 0

    # Database XP must remain 0
    db = DatabaseManager()
    assert db.get_user_xp(TEST_STUDENT_ID) == 0

