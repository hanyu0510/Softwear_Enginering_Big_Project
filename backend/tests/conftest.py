from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import Base, get_db
from app.main import app


@pytest.fixture
def settings(tmp_path):
    return Settings(
        app_env="development",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        upload_dir=tmp_path / "uploads",
        wardrobe_ai_provider="mock",
        _env_file=None,
    )


@pytest.fixture
def db_session(settings):
    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with testing_session() as session:
        yield session
    engine.dispose()


@pytest.fixture
def client(settings, db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth():
    return lambda user="user_a": {"Authorization": f"Bearer dev:{user}"}


@pytest.fixture
def image_bytes():
    output = BytesIO()
    Image.new("RGB", (64, 64), "#d8c4a8").save(output, format="JPEG")
    return output.getvalue()


@pytest.fixture
def transparent_palette_image_bytes():
    output = BytesIO()
    image = Image.new("P", (32, 32), 0)
    image.putpalette([255, 255, 255, 216, 95, 67] + [0, 0, 0] * 254)
    image.info["transparency"] = 0
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def upload_image(client, auth, image_bytes):
    def upload(user="user_a"):
        response = client.post(
            "/api/v1/uploads/image",
            headers=auth(user),
            files={"file": ("coat.jpg", image_bytes, "image/jpeg")},
        )
        assert response.status_code == 200, response.text
        return response.json()["data"]

    return upload


@pytest.fixture
def create_item(client, auth, upload_image):
    def create(user="user_a", **changes):
        uploaded = upload_image(user)
        payload = {
            "name": "米白针织衫",
            "category": "tops",
            "color": "米白",
            "warmth": 2,
            "season": ["spring", "autumn"],
            "style": ["minimal"],
            "occasion": ["casual"],
            "visibility": "private",
            "imageFileId": uploaded["fileId"],
        }
        payload.update(changes)
        response = client.post("/api/v1/items", headers=auth(user), json=payload)
        assert response.status_code == 201, response.text
        return response.json()["data"]

    return create
