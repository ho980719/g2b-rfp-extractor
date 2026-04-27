import json
import shutil
import tempfile
import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from locks import pre_spec_process_lock, pre_spec_extract_lock
from models import PreSpec
from services.converter import prepare_pdf
from services.dify_client import upload_pre_spec_to_knowledge, run_keyword_workflow, update_metadata
from services.g2b_client import fetch_pre_specs
from services.pdf_extractor import extract_text

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pre-specs", tags=["pre-specs"])


def _parse_datetime(s: str | None) -> datetime | None:
    """'YYYY-MM-DD HH:MM:SS' 또는 None → datetime"""
    if not s:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    return None


@router.post("/sync")
async def sync_pre_specs(db: Session = Depends(get_db)):
    """
    G2B 사전규격 API(용역+물품) 호출 후 tb_pre_specs에 신규 건만 bulk insert.
    변경된 공고(chg_dt 갱신)는 업데이트하지 않음 — 별도 갱신 엔드포인트 필요 시 추가.
    """
    items = await fetch_pre_specs(["Servc", "Thng"])

    if not items:
        return {"total": 0, "inserted": 0, "skipped": 0}

    valid_items = [i for i in items if i.get("bfSpecRgstNo")]
    skipped = len(items) - len(valid_items)

    # 기존 레코드 일괄 조회 (N+1 제거)
    keys = {i["bfSpecRgstNo"] for i in valid_items}
    existing_keys = {
        r[0]
        for r in db.query(PreSpec.bf_spec_rgst_no)
        .filter(PreSpec.bf_spec_rgst_no.in_(keys))
        .all()
    }

    new_records = []
    for item in valid_items:
        pk = item["bfSpecRgstNo"]
        if pk in existing_keys:
            skipped += 1
            continue

        spec_urls = item.get("_parsed_spec_urls") or []
        has_spec_doc = bool(spec_urls)

        asign_bdgt_amt = None
        try:
            raw = item.get("asignBdgtAmt") or ""
            asign_bdgt_amt = int(str(raw).replace(",", "")) if raw else None
        except (ValueError, TypeError):
            pass

        dlvr_daynum = None
        try:
            raw = item.get("dlvrDaynum") or ""
            dlvr_daynum = int(str(raw)) if raw else None
        except (ValueError, TypeError):
            pass

        new_records.append(PreSpec(
            bf_spec_rgst_no    = pk,
            bsns_div_nm        = item.get("bsnsDivNm"),
            ref_no             = item.get("refNo"),
            prdct_clsfc_no_nm  = item.get("prdctClsfcNoNm"),
            order_instt_nm     = item.get("orderInsttNm"),
            rl_dminstt_nm      = item.get("rlDminsttNm"),
            asign_bdgt_amt     = asign_bdgt_amt,
            rcpt_dt            = _parse_datetime(item.get("rcptDt")),
            opnin_rgst_clse_dt = _parse_datetime(item.get("opninRgstClseDt")),
            ofcl_tel_no        = item.get("ofclTelNo"),
            ofcl_nm            = item.get("ofclNm"),
            sw_biz_obj_yn      = item.get("swBizObjYn") or "N",
            dlvr_tmlmt_dt      = _parse_datetime(item.get("dlvrTmlmtDt")),
            dlvr_daynum        = dlvr_daynum,
            spec_doc_file_urls = spec_urls if spec_urls else None,
            has_spec_doc       = has_spec_doc,
            prdct_dtl_list     = item.get("prdctDtlList"),
            bid_ntce_no_list   = item.get("bidNtceNoList"),
            rgst_dt            = _parse_datetime(item.get("rgstDt")),
            chg_dt             = _parse_datetime(item.get("chgDt")),
            file_status        = "PENDING" if has_spec_doc else "SKIPPED",
            keyword_status     = "PENDING",
            raw_json           = json.dumps(item, ensure_ascii=False),
        ))

    try:
        db.bulk_save_objects(new_records)
        db.commit()
    except Exception as e:
        db.rollback()
        raise

    logger.info(f"사전규격 sync 완료: total={len(items)} inserted={len(new_records)} skipped={skipped}")
    return {"total": len(items), "inserted": len(new_records), "skipped": skipped}


@router.post("/process-files")
async def process_pre_spec_files(limit: int = 50, db: Session = Depends(get_db)):
    """
    file_status = PENDING 인 사전규격의 규격문서(spec_doc_file_urls[0])를
    PDF로 변환 후 Dify 지식DB에 업로드.
    """
    if pre_spec_process_lock.locked():
        logger.info("pre-specs/process-files 이미 실행 중, 스킵")
        return {"skipped": True, "reason": "already running"}

    async with pre_spec_process_lock:
        pending = (
            db.query(PreSpec)
            .filter(PreSpec.file_status == "PENDING")
            .limit(limit)
            .all()
        )

        done, failed = 0, 0

        for ps in pending:
            ps.file_status = "PROCESSING"
            db.commit()

            # 규격문서 첫 번째 URL 사용
            spec_url = (ps.spec_doc_file_urls or [None])[0]
            if not spec_url:
                ps.file_status = "SKIPPED"
                db.commit()
                continue

            tmpdir = tempfile.mkdtemp()
            try:
                pdf_path = await prepare_pdf(spec_url, tmpdir)
                dify_doc_id = await upload_pre_spec_to_knowledge(pdf_path, ps)

                ps.file_status = "DONE"
                ps.file_processed_at = datetime.utcnow()
                ps.dify_doc_id = dify_doc_id
                ps.file_error_msg = None
                done += 1
                logger.info(f"사전규격 파일 처리 완료: {ps.bf_spec_rgst_no}")

            except Exception as e:
                ps.file_status = "FAILED"
                ps.file_error_msg = str(e)[:500]
                failed += 1
                logger.error(f"사전규격 파일 처리 실패: {ps.bf_spec_rgst_no} | {e}")

            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
                db.commit()

        return {"total": len(pending), "done": done, "failed": failed}


@router.post("/extract-keywords")
async def extract_pre_spec_keywords(limit: int = 50, db: Session = Depends(get_db)):
    """
    keyword_status = PENDING 이고 file_status IN (DONE, SKIPPED, FAILED) 인
    사전규격의 키워드 추출.
    규격문서가 있으면 텍스트 추출 후 LLM 워크플로우 호출,
    없으면(SKIPPED) 품목/용역분류명만으로 키워드 추출.
    """
    if pre_spec_extract_lock.locked():
        logger.info("pre-specs/extract-keywords 이미 실행 중, 스킵")
        return {"skipped": True, "reason": "already running"}

    async with pre_spec_extract_lock:
        pending = (
            db.query(PreSpec)
            .filter(
                PreSpec.keyword_status == "PENDING",
                PreSpec.file_status.in_(["DONE", "SKIPPED", "FAILED"]),
            )
            .limit(limit)
            .all()
        )

        done, failed = 0, 0

        for ps in pending:
            tmpdir = tempfile.mkdtemp()
            try:
                rfp_text = ""
                spec_url = (ps.spec_doc_file_urls or [None])[0]
                if ps.file_status == "DONE" and spec_url:
                    try:
                        pdf_path = await prepare_pdf(spec_url, tmpdir)
                        rfp_text = extract_text(pdf_path)
                    except Exception as e:
                        logger.warning(f"사전규격 텍스트 추출 실패, 품목명으로만 추출: {ps.bf_spec_rgst_no} | {e}")

                keywords = await run_keyword_workflow(
                    bid_title=ps.prdct_clsfc_no_nm or "",
                    rfp_text=rfp_text,
                )

                if not keywords:
                    ps.keyword_status = "FAILED"
                    failed += 1
                    logger.warning(f"사전규격 키워드 추출 빈 배열: {ps.bf_spec_rgst_no}")
                    continue

                ps.keywords = keywords
                ps.keyword_status = "DONE"
                ps.keyword_extracted_at = datetime.utcnow()
                done += 1
                logger.info(f"사전규격 키워드 추출 완료: {ps.bf_spec_rgst_no} → {keywords}")

                if ps.dify_doc_id:
                    try:
                        await update_metadata(ps.dify_doc_id, {"keywords": ", ".join(keywords)})
                    except Exception as e:
                        logger.warning(f"Dify 메타데이터 업데이트 실패 (무시): {ps.bf_spec_rgst_no} | {e}")

            except Exception as e:
                ps.keyword_status = "FAILED"
                failed += 1
                logger.error(f"사전규격 키워드 추출 실패: {ps.bf_spec_rgst_no} | {e}")

            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)
                db.commit()

        return {"total": len(pending), "done": done, "failed": failed}