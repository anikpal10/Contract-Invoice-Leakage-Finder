import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models.organization import Organization, Workspace
from backend.app.models.user import User, UserRole

# Use in-memory SQLite for high-speed, isolated test execution
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_tenants(db_session):
    # Tenant 1: Acme Corp
    org1 = Organization(name="Acme Corp", slug="acme-corp")
    db_session.add(org1)
    db_session.flush()

    user1 = User(
        organization_id=org1.id,
        email="admin@acme.com",
        hashed_password=get_password_hash("Secret123!"),
        full_name="Alice Admin",
        role=UserRole.ADMIN.value,
        is_active=True
    )
    db_session.add(user1)
    
    ws1 = Workspace(organization_id=org1.id, name="Acme Default WS")
    db_session.add(ws1)

    # Tenant 2: Beta Industries
    org2 = Organization(name="Beta Industries", slug="beta-industries")
    db_session.add(org2)
    db_session.flush()

    user2 = User(
        organization_id=org2.id,
        email="bob@beta.com",
        hashed_password=get_password_hash("Secret456!"),
        full_name="Bob Beta",
        role=UserRole.REVIEWER.value,
        is_active=True
    )
    db_session.add(user2)

    ws2 = Workspace(organization_id=org2.id, name="Beta Default WS")
    db_session.add(ws2)

    db_session.commit()

    token1 = create_access_token(data={"sub": user1.id, "org": org1.id, "role": user1.role})
    token2 = create_access_token(data={"sub": user2.id, "org": org2.id, "role": user2.role})

    return {
        "org1": org1,
        "user1": user1,
        "token1": token1,
        "ws1": ws1,
        "org2": org2,
        "user2": user2,
        "token2": token2,
        "ws2": ws2,
    }

