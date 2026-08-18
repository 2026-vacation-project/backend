import time
import jwt
import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET_KEY = "YOUR_SUPER_SECRET_KEY_CHANGE_THIS"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# OAuth Client 정보 (발급받은 실제 값으로 대체)
GOOGLE_CLIENT_ID = "YOUR_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET = "YOUR_GOOGLE_CLIENT_SECRET"
GOOGLE_REDIRECT_URI = "http://localhost:3000/auth/callback/google"

DISCORD_CLIENT_ID = "YOUR_DISCORD_CLIENT_ID"
DISCORD_CLIENT_SECRET = "YOUR_DISCORD_CLIENT_SECRET"
DISCORD_REDIRECT_URI = "http://localhost:3000/auth/callback/discord"

security = HTTPBearer()

class SnowflakeGenerator:
    def __init__(self, machine_id=1):
        self.machine_id = machine_id
        self.sequence = 0
        self.last_timestamp = -1

    def generate_id(self) -> int:
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
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="유효하지 않은 토큰입니다.")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰이 만료되었습니다.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="토큰 인증에 실패했습니다.")

async def fetch_oauth_user_info(provider: str, code: str) -> dict:
    async with httpx.AsyncClient() as client:
        if provider.lower() == "google":
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
                raise HTTPException(status_code=400, detail="Google OAuth 인증 실패")
            
            access_token = token_res.json().get("access_token")
            user_res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            info = user_res.json()
            return {"email": info["email"], "name": info.get("name", "User"), "profile_image": info.get("picture")}

        elif provider.lower() == "discord":
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
                raise HTTPException(status_code=400, detail="Discord OAuth 인증 실패")
            
            access_token = token_res.json().get("access_token")
            user_res = await client.get(
                "https://discord.com/api/v10/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            info = user_res.json()
            avatar_url = f"https://cdn.discordapp.com/avatars/{info['id']}/{info['avatar']}.png" if info.get("avatar") else None
            return {"email": info["email"], "name": info.get("username"), "profile_image": avatar_url}

        else:
            raise HTTPException(status_code=400, detail="지원하지 않는 로그인 제공자입니다.")

def send_fcm_notification(tokens: list[str], title: str, body: str):
    if not tokens:
        return
    print(f"\n[FCM 알림 발송 완료] 수신: {len(tokens)}명 | {title}: {body}\n")