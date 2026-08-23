import os
import json
import logging
import time
from threading import Lock
from urllib.parse import urlparse
import firebase_admin
import jwt
import httpx
from firebase_admin import credentials, messaging
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from sqlalchemy.orm import Session

import database
import models

# .env 파일 로드 (backend 루트 및 상위 경로 탐색)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.getenv("SECRET_KEY", "YOUR_SUPER_SECRET_KEY_CHANGE_THIS")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_DAYS = int(os.getenv("ACCESS_TOKEN_EXPIRE_DAYS", "7"))

# OAuth Client 정보
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback/google")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:3000/auth/callback/discord")

FIREBASE_SERVICE_ACCOUNT_JSON = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")

logger = logging.getLogger(__name__)
_firebase_app_lock = Lock()

security = HTTPBearer()

class SnowflakeGenerator:
    def __init__(self, machine_id=1):
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1
        self._lock = Lock()

    def generate_id(self) -> int:
        with self._lock:
            timestamp = int(time.time() * 1000)
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 4095
            else:
                self.sequence = 0
            self.last_timestamp = timestamp
            return ((timestamp - 1609459200000) << 22) | (self.machine_id << 12) | self.sequence

snowflake = SnowflakeGenerator()

def generate_custom_id(provider: str) -> str:
    sf_id = snowflake.generate_id()
    prefix = "G-" if provider.lower() == "google" else "D-"
    return f"{prefix}{sf_id}"

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def resolve_access_token(token: str, db: Session) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")
        token_version = payload.get("ver", 0)
        if not isinstance(token_version, int):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or user.auth_version != token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="다시 로그인해 주세요.",
            )
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 인증에 실패했습니다.")


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(database.get_db),
) -> str:
    return resolve_access_token(credentials.credentials, db)

async def fetch_oauth_user_info(provider: str, code: str) -> dict:
    async with httpx.AsyncClient() as client:
        if provider.lower() == "google":
            if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Google OAuth 설정(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET)이 .env 파일에 구성되지 않았습니다."
                )
            token_res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            if token_res.status_code != 200:
                error_detail = token_res.text
                raise HTTPException(status_code=400, detail=f"Google OAuth 인증 실패: {error_detail}")
            
            access_token = token_res.json().get("access_token")
            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if user_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Google 유저 정보 조회 실패")
            info = user_res.json()
            display_name = info.get("name") or "User"
            return {
                "email": info["email"],
                "name": display_name,
                "display_name": display_name,
                "profile_image": info.get("picture"),
            }

        elif provider.lower() == "discord":
            if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Discord OAuth 설정(DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET)이 .env 파일에 구성되지 않았습니다."
                )
            token_res = await client.post(
                "https://discord.com/api/v10/oauth2/token",
                data={
                    "code": code,
                    "client_id": DISCORD_CLIENT_ID,
                    "client_secret": DISCORD_CLIENT_SECRET,
                    "redirect_uri": DISCORD_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_res.status_code != 200:
                error_detail = token_res.text
                raise HTTPException(status_code=400, detail=f"Discord OAuth 인증 실패: {error_detail}")
            
            access_token = token_res.json().get("access_token")
            user_res = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if user_res.status_code != 200:
                raise HTTPException(status_code=400, detail="Discord 유저 정보 조회 실패")
            info = user_res.json()
            avatar_url = f"https://cdn.discordapp.com/avatars/{info['id']}/{info['avatar']}.png" if info.get("avatar") else None
            username = info.get("username") or info.get("global_name") or "User"
            return {
                "email": info["email"],
                "name": username,
                "display_name": info.get("global_name") or username,
                "profile_image": avatar_url,
                "provider_user_id": str(info["id"]),
            }

        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 로그인 제공자입니다.")

def _get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        pass

    with _firebase_app_lock:
        try:
            return firebase_admin.get_app()
        except ValueError:
            credential = None
            if FIREBASE_SERVICE_ACCOUNT_JSON:
                credential = credentials.Certificate(json.loads(FIREBASE_SERVICE_ACCOUNT_JSON))
            return firebase_admin.initialize_app(credential)


def send_fcm_notification(
    installation_ids: list[str],
    title: str,
    body: str,
    link: str | None = None,
) -> int:
    targets = list(dict.fromkeys(target.strip() for target in installation_ids if target.strip()))
    if not targets:
        return 0

    try:
        app = _get_firebase_app()
        success_count = 0
        notification_link = link if link and urlparse(link).scheme == "https" else None
        for offset in range(0, len(targets), 500):
            batch = targets[offset : offset + 500]
            webpush = messaging.WebpushConfig(
                notification=messaging.WebpushNotification(
                    title=title,
                    body=body,
                    icon="/favicon.png",
                ),
                fcm_options=messaging.WebpushFCMOptions(link=notification_link) if notification_link else None,
            )
            message = messaging.MulticastMessage(
                fids=batch,
                notification=messaging.Notification(title=title, body=body),
                data={"url": link} if link else None,
                webpush=webpush,
            )
            response = messaging.send_each_for_multicast(message, app=app)
            success_count += response.success_count

            for target, send_response in zip(batch, response.responses, strict=True):
                if not send_response.success:
                    logger.warning("FCM 알림 전송 실패: target=%s error=%s", target, send_response.exception)

        logger.info("FCM 알림 전송 완료: success=%d total=%d", success_count, len(targets))
        return success_count
    except Exception:
        logger.exception("FCM 알림을 전송하지 못했습니다.")
        return 0
