from pydantic import BaseModel


class BidSyncResponse(BaseModel):
    total: int
    inserted: int
    skipped: int
