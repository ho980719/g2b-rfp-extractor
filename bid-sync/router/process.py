import shutil
import tempfile
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from locks import process_lock
from models import Bid
from services.converter import prepare_pdf
from services.dify_client import upload_to_knowledge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bids", tags=["process"])


@router.post("/process-files")
async def process_files(limit: int = 10, db: Session = Depends(get_db)):
    """
    file_status = PENDING 인 공고의 RFP 파일을 변환 후 Dify 지식DB에 업로드.
    이미 실행 중이면 즉시 반환.
    """
    if process_lock.locked():
        logger.info("process-files 이미 실행 중, 스킵")
        return {"skipped": True, "reason": "already running"}

    async with process_lock:
        pending = (
            db.query(Bid)
            .filter(Bid.file_status == "PENDING")
            .limit(limit)
            .all()
        )

        done, failed = 0, 0

        for bid in pending:
            bid.file_status = "PROCESSING"
            db.commit()

            tmpdir = tempfile.mkdtemp()
            try:
                pdf_path = await prepare_pdf(bid.rfp_file_url, tmpdir)

                dify_doc_id = await upload_to_knowledge(pdf_path, bid)

                bid.file_status = "DONE"
                bid.file_processed_at = datetime.utcnow()
                bid.dify_doc_id = dify_doc_id
                bid.file_error_msg = None
                done += 1
                logger.info(f"처리 완료: {bid.bid_ntce_no}")

            except Exception as e:
                bid.file_status = "FAILED"
                bid.file_error_msg = str(e)[:500]
                failed += 1
                logger.error(f"처리 실패: {bid.bid_ntce_no} | {e}")

            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
                db.commit()

        return {"total": len(pending), "done": done, "failed": failed}