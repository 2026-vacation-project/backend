from main import app
from models import Room


def test_room_unit_type_is_removed_from_database_and_api() -> None:
    assert "unit_type" not in Room.__table__.columns

    schemas = app.openapi()["components"]["schemas"]
    for schema_name in ("RoomCreate", "RoomUpdate", "RoomResponse"):
        assert "unit_type" not in schemas[schema_name].get("properties", {})


def test_room_api_exposes_recruiting_tags() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert "tag_ids" in schemas["RoomCreate"]["properties"]
    assert "tag_ids" in schemas["RoomUpdate"]["properties"]
    assert "tags" in schemas["RoomResponse"]["properties"]
    assert "user_ids" in schemas["RoleResponse"]["properties"]
