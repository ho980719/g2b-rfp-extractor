from fastapi import FastAPI
from database import engine, Base
from router import bids

Base.metadata.create_all(bind=engine)  # 테이블 자동 생성

app = FastAPI(title="나라장터 공고 Sync API")
app.include_router(bids.router)

@app.get("/health")
def health():
    return {"status": "ok"}