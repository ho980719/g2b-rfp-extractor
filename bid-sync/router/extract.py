import shutil
import tempfile
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from locks import extract_lock
from models import Bid
from services.converter import prepare_pdf
from services.pdf_extractor import extract_text
from services.dify_client import run_keyword_workflow, update_metadata

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bids", tags=["extract"])


@router.post("/extract-keywords")
async def extract_keywords(limit: int = 10, db: Session = Depends(get_db)):
    """
    keyword_status = PENDING 이고 file_status = DONE 인 공고의 키워드 추출.
    RFP PDF 텍스트 → Dify 워크플로우 → keywords 저장 + Dify 메타데이터 업데이트.
    이미 실행 중이면 즉시 반환.
    """
    if extract_lock.locked():
        logger.info("extract-keywords 이미 실행 중, 스킵")
        return {"skipped": True, "reason": "already running"}

    async with extract_lock:
        pending = (
            db.query(Bid)
            .filter(
                Bid.keyword_status == "PENDING",
                Bid.file_status.in_(["DONE", "SKIPPED", "FAILED"]),
            )
            .limit(limit)
            .all()
        )

        done, failed = 0, 0

        for bid in pending:
            tmpdir = tempfile.mkdtemp()
            try:
                rfp_text = ""
                if bid.file_status == "DONE" and bid.rfp_file_url:
                    try:
                        pdf_path = await prepare_pdf(bid.rfp_file_url, tmpdir)
                        rfp_text = extract_text(pdf_path)
                    except Exception as e:
                        logger.warning(f"텍스트 추출 실패, 공고명만으로 키워드 추출: {bid.bid_ntce_no} | {e}")

                keywords = await run_keyword_workflow(
                    bid_title=bid.bid_ntce_nm or "",
                    rfp_text=rfp_text,
                )

                bid.keywords = keywords
                bid.keyword_status = "DONE"
                bid.keyword_extracted_at = datetime.utcnow()
                done += 1
                logger.info(f"키워드 추출 완료: {bid.bid_ntce_no} → {keywords}")

                # Dify 메타데이터 업데이트 실패해도 keyword_status는 DONE 유지
                if bid.dify_doc_id:
                    try:
                        await update_metadata(bid.dify_doc_id, {"keywords": ", ".join(keywords)})
                    except Exception as e:
                        logger.warning(f"Dify 메타데이터 업데이트 실패 (무시): {bid.bid_ntce_no} | {e}")

            except Exception as e:
                bid.keyword_status = "FAILED"
                failed += 1
                logger.error(f"키워드 추출 실패: {bid.bid_ntce_no} | {e}")

            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
                db.commit()

        return {"total": len(pending), "done": done, "failed": failed}