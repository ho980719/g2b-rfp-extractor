import logging

from fastapi import FastAPI

from router import bids, convert, process, extract

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="나라장터 공고 Sync API")
app.include_router(bids.router)
app.include_router(convert.router)
app.include_router(process.router)
app.include_router(extract.router)


@app.get("/health")
def health():
    return {"status": "ok"}
