from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

import igdb
import schemas
import utils


router = APIRouter(prefix="/api/v1/games", tags=["Games"])


@router.get("/search", response_model=list[schemas.GameSearchResult])
async def search_games(
    query: Annotated[str, Query(min_length=1, max_length=100, description="검색할 게임 이름")],
    limit: Annotated[int, Query(ge=1, le=20, description="반환할 최대 게임 수")] = 10,
    _current_user_id: str = Depends(utils.get_current_user_id),
    client: igdb.IGDBClient = Depends(igdb.get_igdb_client),
):
    normalized_query = query.strip()
    if not normalized_query:
        raise HTTPException(status_code=422, detail="검색어를 입력해 주세요.")

    try:
        return await client.search_games(normalized_query, limit)
    except igdb.IGDBClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
