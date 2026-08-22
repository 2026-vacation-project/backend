from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
sys.path.insert(0, str(PROJECT_DIR))
sys.path.insert(0, str(BACKEND_DIR))

import models  # noqa: E402,F401
from database import Base  # noqa: E402
from games import models as game_models  # noqa: E402,F401


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def elden_ring_payload():
    return {
        "id": 119133,
        "name": "Elden Ring",
        "slug": "elden-ring",
        "first_release_date": 1645747200,
        "rating": 95.0,
        "alternative_names": [
            {"name": "엘든링", "comment": "alias"},
            {"name": "EldenRing", "comment": "alternative"},
        ],
        "game_localizations": [
            {
                "name": "엘든 링",
                "region": {"identifier": "kr", "name": "South Korea"},
            }
        ],
        "platforms": [{"id": 6, "name": "PC (Microsoft Windows)", "abbreviation": "PC"}],
        "genres": [{"id": 12, "name": "Role-playing (RPG)"}],
        "involved_companies": [
            {
                "developer": True,
                "publisher": False,
                "company": {"id": 101, "name": "FromSoftware"},
            }
        ],
        "cover": {"image_id": "co4jni", "width": 264, "height": 374},
        "artworks": [],
        "screenshots": [],
        "external_games": [
            {
                "external_game_source": {"name": "Steam"},
                "uid": "1245620",
                "name": "ELDEN RING",
            }
        ],
    }
