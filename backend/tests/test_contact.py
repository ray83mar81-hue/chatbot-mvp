"""Tests for the contact form endpoints."""
import json


def _submit(client, **overrides):
    """Helper: submit a valid contact form, with optional overrides."""
    payload = {
        "business_id": 1,
        "session_id": "contact-test",
        "name": "Juan Pérez",
        "phone": "+34 600 123 456",
        "email": "juan@example.com",
        "message": "Quiero reservar para 10 personas",
        "language": "es",
        "whatsapp_opt_in": False,
        "privacy_accepted": True,
        "honeypot": "",
    }
    payload.update(overrides)
    return client.post("/contact/submit", json=payload)


# ── Public config ─────────────────────────────────────


def test_contact_config_enabled(client):
    res = client.get("/business/1/contact-config")
    assert res.status_code == 200
    data = res.json()
    assert data["contact_form_enabled"] is True
    assert data["whatsapp_enabled"] is True
    assert data["privacy_url"] == "https://test.com/privacy"


def test_contact_config_not_found(client):
    res = client.get("/business/9999/contact-config")
    assert res.status_code == 404


# ── Submit ────────────────────────────────────────────


def test_submit_valid(client):
    res = _submit(client, session_id="submit-ok-1")
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Juan Pérez"
    assert data["status"] == "new"
    assert data["id"] > 0


def test_submit_with_whatsapp(client):
    res = _submit(client, session_id="submit-wa-1", whatsapp_opt_in=True)
    assert res.status_code == 200
    assert res.json()["whatsapp_opt_in"] is True


def test_submit_links_conversation(client):
    """If the session has a conversation, the contact should be linked."""
    # Create a conversation first
    client.post("/chat/message", json={
        "message": "hola", "session_id": "conv-link-1", "business_id": 1, "language": "es",
    })
    res = _submit(client, session_id="conv-link-1")
    assert res.status_code == 200
    assert res.json()["conversation_id"] is not None


# ── Validation ────────────────────────────────────────


def test_submit_privacy_required(client):
    res = _submit(client, session_id="val-1", privacy_accepted=False)
    assert res.status_code == 422
    assert "privacy" in res.json()["detail"].lower()


def test_submit_empty_name_rejected(client):
    res = _submit(client, session_id="val-2", name="  ")
    assert res.status_code == 422


def test_submit_bad_phone_rejected(client):
    res = _submit(client, session_id="val-3", phone="12")
    assert res.status_code == 422


def test_submit_empty_message_rejected(client):
    res = _submit(client, session_id="val-4", message="  ")
    assert res.status_code == 422


# ── Anti-spam ─────────────────────────────────────────


def test_honeypot_silently_rejected(client):
    res = _submit(client, session_id="spam-1", honeypot="gotcha")
    assert res.status_code == 200
    assert res.json()["id"] == 0  # fake ID, not saved

    # Verify nothing was actually saved for this session
    all_contacts = client.get("/contact/requests?business_id=1").json()
    for c in all_contacts:
        assert c["name"] != "Juan Pérez" or c["id"] != 0


def test_rate_limit(client):
    """4th submit from the same session within the rate window should be blocked."""
    for i in range(3):
        res = _submit(client, session_id="rate-test", name=f"User{i}")
        assert res.status_code == 200, f"Submit {i+1} should succeed"

    res = _submit(client, session_id="rate-test", name="User4")
    assert res.status_code == 429


def test_form_disabled(client):
    """Submit should be rejected if contact_form_enabled is false."""
    # Disable it
    client.put("/business/1", json={"contact_form_enabled": False})
    res = _submit(client, session_id="disabled-1")
    assert res.status_code == 403
    # Re-enable for other tests
    client.put("/business/1", json={"contact_form_enabled": True})


# ── Admin CRUD ────────────────────────────────────────


def test_list_contacts(client):
    _submit(client, session_id="list-1")
    res = client.get("/contact/requests?business_id=1")
    assert res.status_code == 200
    assert len(res.json()) >= 1


def test_list_contacts_filter_status(client):
    _submit(client, session_id="filter-1")
    contacts = client.get("/contact/requests?business_id=1&status=new").json()
    assert all(c["status"] == "new" for c in contacts)


def test_get_contact_detail(client):
    cid = _submit(client, session_id="detail-1").json()["id"]
    res = client.get(f"/contact/requests/{cid}")
    assert res.status_code == 200
    assert res.json()["name"] == "Juan Pérez"


def test_update_contact_status(client):
    cid = _submit(client, session_id="update-1").json()["id"]
    res = client.put(f"/contact/requests/{cid}", json={
        "status": "contacted",
        "notes": "Llamé y confirmó",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "contacted"
    assert res.json()["notes"] == "Llamé y confirmó"


def test_update_invalid_status(client):
    cid = _submit(client, session_id="inv-status-1").json()["id"]
    res = client.put(f"/contact/requests/{cid}", json={"status": "invalid"})
    assert res.status_code == 422


def test_delete_contact_gdpr(client):
    cid = _submit(client, session_id="delete-1").json()["id"]
    res = client.delete(f"/contact/requests/{cid}")
    assert res.status_code == 200

    # Verify gone
    res = client.get(f"/contact/requests/{cid}")
    assert res.status_code == 404


def test_delete_contact_not_found(client):
    res = client.delete("/contact/requests/99999")
    assert res.status_code == 404
