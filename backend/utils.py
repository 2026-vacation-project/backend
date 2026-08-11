import time
from fastapi import BackgroundTasks

# 간이 Snowflake ID 생성기
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

# FCM 백그라운드 전송 로직
def send_fcm_notification(tokens: list[str], title: str, body: str):
    if not tokens:
        return
    # Firebase Admin SDK 연동 위치
    print(f"\n[FCM 알림 발송 완료]")
    print(f" - 수신 대상 수: {len(tokens)}명")
    print(f" - 제목: {title}")
    print(f" - 내용: {body}\n")