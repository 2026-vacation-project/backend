import unicodedata


def normalize_game_name(value: str) -> str:
    """Normalize a game name for matching without changing the stored original."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())
