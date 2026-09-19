def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"name": "Sam", "email": "Sam@Example.com", "password": "Passw0rdX"})
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "sam@example.com"  # normalised

    login = client.post("/api/auth/login", json={"email": "SAM@example.com", "password": "Passw0rdX"})
    assert login.status_code == 200
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.json()["name"] == "Sam"


def test_weak_passwords_rejected(client):
    for pw in ["short1", "nodigitshere", "12345678"]:
        r = client.post("/api/auth/register", json={"name": "S", "email": "a@example.com", "password": pw})
        assert r.status_code == 422, pw
        assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_duplicate_email(client):
    body = {"name": "S", "email": "dup@example.com", "password": "Passw0rdX"}
    assert client.post("/api/auth/register", json=body).status_code == 200
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 400
    assert r.json()["detail"]["error"]["code"] == "EMAIL_TAKEN"


def test_login_rate_limited_after_five_failures(client, auth):
    bad = {"email": "student@example.com", "password": "wrong-pass-1"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=bad).status_code == 401
    r = client.post("/api/auth/login", json=bad)
    assert r.status_code == 429
    # even the right password is blocked until the window passes
    good = {"email": "student@example.com", "password": "Passw0rdX"}
    assert client.post("/api/auth/login", json=good).status_code == 429


def test_protected_routes_need_token(client):
    assert client.get("/api/exams").status_code == 401
