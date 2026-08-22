from main import app
from models import Room


def test_room_unit_type_is_removed_from_database_and_api() -> None:
    assert "unit_type" not in Room.__table__.columns

    schemas = app.openapi()["components"]["schemas"]
    for schema_name in ("RoomCreate", "RoomUpdate", "RoomResponse"):
        assert "unit_type" not in schemas[schema_name].get("properties", {})
