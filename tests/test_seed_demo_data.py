"""Datos de demostración para PostgreSQL local: repetibles, sin duplicados y nunca en servidores."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from scripts.seed_demo_data import DEMO_PASSWORD, seed_demo


def test_demo_data_is_repeatable_and_enables_login(session_factory, client):
    from app.models import Appointment, KnowledgeDocument, Professional, User
    url = make_url("sqlite:///demo.sqlite3")
    now = datetime(2030, 1, 7, 8, 0, tzinfo=ZoneInfo("America/Costa_Rica"))
    first = seed_demo(session_factory, url, now)
    assert any("citas" in line for line in first)
    seed_demo(session_factory, url, now)
    with session_factory() as session:
        count = lambda model: session.scalar(select(func.count()).select_from(model))
        assert count(Professional) == 3 and count(Appointment) == 6 and count(KnowledgeDocument) == 6
        assert session.scalar(select(func.count()).select_from(User).where(User.email == "alfa@example.com")) == 1
    response = client.post("/auth/login", json={"email": "alfa@example.com", "password": DEMO_PASSWORD},
                           headers={"Origin": "http://testserver"})
    assert response.status_code in (200, 204), response.text


def test_refuses_remote_databases(session_factory):
    with pytest.raises(SystemExit):
        seed_demo(session_factory, make_url("postgresql+psycopg://u:p@db.example.com/orqentiva"))
