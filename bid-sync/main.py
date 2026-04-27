import logging
import os

from fastapi import FastAPI

from router import bids, convert, process, extract, matching, pre_specs

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)

# 노이즈 라이브러리 로그 억제
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

app = FastAPI(title="나라장터 공고 Sync API")
app.include_router(bids.router)
app.include_router(convert.router)
app.include_router(process.router)
app.include_router(extract.router)
app.include_router(matching.router)
app.include_router(pre_specs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
