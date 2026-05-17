import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

SQLITE_URL = "sqlite:///./test.db"

engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def mock_redis():
    with patch("app.cache.redis_client") as mock:
        mock.get.return_value = None
        mock.setex.return_value = True
        mock.incr.return_value = 1
        yield mock


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shorten_url(client):
    response = client.post(
        "/shorten",
        json={"url": "https://www.github.com"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "short_code" in data
    assert len(data["short_code"]) == 6
    assert data["original_url"] == "https://www.github.com/"


def test_shorten_same_url_twice(client):
    payload = {"url": "https://www.github.com"}
    r1 = client.post("/shorten", json=payload)
    r2 = client.post("/shorten", json=payload)
    assert r1.json()["short_code"] == r2.json()["short_code"]


def test_redirect(client):
    create = client.post("/shorten", json={"url": "https://www.github.com"})
    code = create.json()["short_code"]

    response = client.get(f"/{code}", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://www.github.com/"


def test_stats(client):
    create = client.post("/shorten", json={"url": "https://www.github.com"})
    code = create.json()["short_code"]

    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    stats = client.get(f"/stats/{code}")
    assert stats.status_code == 200
    assert stats.json()["clicks"] == 2


def test_invalid_url(client):
    response = client.post("/shorten", json={"url": "not-a-url"})
    assert response.status_code == 422


def test_unknown_code(client):
    response = client.get("/stats/doesnotexist")
    assert response.status_code == 404