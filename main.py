import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from fastapi import FastAPI

from games import models as game_models  # noqa: F401
import models
from routers import auth, games, users, groups, roles, rooms, realtime


app = FastAPI(title="Team Matcher API")

app.include_router(auth.router)
app.include_router(games.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(roles.router)
app.include_router(rooms.router)
app.include_router(realtime.router)


@app.get("/")
def root():
    return {"message": "팀원 모집 백엔드 API 서버가 작동 중입니다."}
