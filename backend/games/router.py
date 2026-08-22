from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

import database
import utils
from games import service
from games.schemas import GameSearchResult


router = APIRouter(prefix="/api/v1/games", tags=["Games"])


@router.get("/search", response_model=list[GameSearchResult])
def search_games(
    query: Annotated[str, Query(min_length=1, max_length=100, description="검색할 게임 이름")],
    limit: Annotated[int, Query(ge=1, le=50, description="반환할 최대 게임 수")] = 20,
    _current_user_id: str = Depends(utils.get_current_user_id),
    db: Session = Depends(database.get_db),
):
    stripped_query = query.strip()
    if not stripped_query:
        raise HTTPException(status_code=422, detail="검색어를 입력해 주세요.")
    return service.search_games(db, stripped_query, limit)
