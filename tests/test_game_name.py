from games.normalization import normalize_game_name


def test_normalize_game_name() -> None:
    assert normalize_game_name("엘든 링") == "엘든링"
    assert normalize_game_name("ELDEN RING") == "eldenring"
    assert normalize_game_name("Cyberpunk: 2077") == "cyberpunk2077"
