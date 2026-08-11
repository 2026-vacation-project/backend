import sys
import os

# Add backend directory to python path for seamless imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import models, database
from routers import auth, users, groups, roles, rooms

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="Team Matcher API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(roles.router)
app.include_router(rooms.router)

@app.get("/")
def root():
    return {"message": "팀원 모집 백엔드 API 서버가 작동 중입니다."}