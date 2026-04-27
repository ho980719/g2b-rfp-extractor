import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID", "")
DIFY_PRE_SPEC_DATASET_ID = os.getenv("DIFY_PRE_SPEC_DATASET_ID", "")  # 사전규격 전용 지식DB
DIFY_KEYWORD_WORKFLOW_KEY = os.getenv("DIFY_KEYWORD_WORKFLOW_KEY", "")
DIFY_REASON_WORKFLOW_KEY = os.getenv("DIFY_REASON_WORKFLOW_KEY", "")

# 입찰공고 지식DB 메타데이터 필드 ID
FIELD_IDS = {
    "bid_no":        "efda07c9-ee86-4f04-b32e-9d4abf7d6a4d",
    "bid_ord":       "35af4325-21ec-4f17-a635-1a69e490c777",
    "bid_kind":      "de6131bb-ce81-4c05-9fab-aba4e886d268",
    "bid_title":     "8f36b8be-3774-4aa5-b5af-b856f96b5f48",
    "org_name":      "2c31b48c-2d45-452e-8c35-9a506dc038f8",
    "bid_date":      "397d393f-aa99-4c5e-b959-5922ee8ee79c",
    "open_date":     "16e08ac3-7c34-46f5-99ee-f6147b70a156",
    "budget":        "9afde289-caee-4843-a4fe-92707b033d8b",
    "award_type":    "8208c990-ee05-461a-9449-406aa969fc2c",
    "detail_url":    "3fbf2de6-b71e-4214-89ec-ddb94dd9c708",
    "bid_clse_dt":   "e277352e-4672-45b5-b3bb-fd1d38937f5b",
    "keywords":      "7bf6efcb-9aac-4914-9a4e-bcef863ecf41",
    "bid_clsfctn_no": "42ffdf20-443c-4455-850e-9093b6b1279c",
}

# 사전규격 지식DB 메타데이터 필드 ID
PRE_SPEC_FIELD_IDS: dict[str, str] = {
    "bid_no":      "6b031b37-c912-47fa-8c5c-36abf54784a6",
    "bid_kind":    "d0b7946b-8605-4070-9517-4ef5861802a3",
    "bid_title":   "96b7015c-294e-4366-b76f-8626464a4b3a",
    "org_name":    "d663451e-aa70-43b3-912f-eb9305f8e09c",
    "bid_date":    "ca80ee60-80d3-4e9b-b3e3-233291f43d57",
    "bid_clse_dt": "6c4af0e0-ebe9-4568-8fd7-dafdf795e4fd",
    "budget":      "eceb7443-f11b-4927-bff3-791820856a81",
    "keywords":    "7f6515ba-135d-4974-969b-8ef90a051bad",
}


async def upload_to_knowledge(pdf_path: Path, bid) -> str:
    """PDF를 Dify 지식DB에 업로드 후 document_id 반환"""
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}

    data = {
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        unique_name = f"{bid.bid_ntce_no}_{bid.bid_ntce_ord}.pdf"
        with open(pdf_path, "rb") as f:
            response = await client.post(
                f"{DIFY_API_URL}/datasets/{DIFY_DATASET_ID}/document/create-by-file",
                headers=headers,
                files={"file": (unique_name, f, "application/pdf")},
                data={"data": json.dumps(data, ensure_ascii=False)},
            )
        response.raise_for_status()

    doc_id = response.json()["document"]["id"]
    logger.info(f"Dify 업로드 완료: {bid.bid_ntce_no} → doc_id={doc_id}")

    # 업로드 후 전체 메타데이터 설정
    await update_metadata(doc_id, {
        "bid_no":        bid.bid_ntce_no or "",
        "bid_ord":       bid.bid_ntce_ord or "",
        "bid_kind":      bid.bid_kind or "",
        "bid_title":     bid.bid_ntce_nm or "",
        "org_name":      bid.ntce_instt_nm or "",
        "bid_date":      bid.bid_ntce_dt or "",
        "open_date":     bid.openg_dt or "",
        "budget":        str(bid.presmpt_prce or ""),
        "award_type":    bid.bid_mtd_nm or "",
        "detail_url":    bid.detail_url or "",
        "bid_clse_dt":   bid.bid_clse_dt or "",
        "bid_clsfctn_no": bid.bid_clsfctn_no or "",
    })

    return doc_id


async def upload_pre_spec_to_knowledge(pdf_path, pre_spec) -> str:
    """사전규격 규격문서 PDF를 사전규격 전용 Dify 지식DB에 업로드 후 document_id 반환"""
    if not DIFY_PRE_SPEC_DATASET_ID:
        raise ValueError("DIFY_PRE_SPEC_DATASET_ID 환경변수가 설정되지 않았습니다.")

    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}
    data = {
        "indexing_technique": "high_quality",
        "process_rule": {"mode": "automatic"},
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        unique_name = f"PS_{pre_spec.bf_spec_rgst_no}.pdf"
        with open(pdf_path, "rb") as f:
            response = await client.post(
                f"{DIFY_API_URL}/datasets/{DIFY_PRE_SPEC_DATASET_ID}/document/create-by-file",
                headers=headers,
                files={"file": (unique_name, f, "application/pdf")},
                data={"data": json.dumps(data, ensure_ascii=False)},
            )
        response.raise_for_status()

    doc_id = response.json()["document"]["id"]
    logger.info(f"Dify 업로드 완료 (사전규격): {pre_spec.bf_spec_rgst_no} → doc_id={doc_id}")

    await update_pre_spec_metadata(doc_id, {
        "bid_no":      pre_spec.bf_spec_rgst_no or "",
        "bid_ord":     "",
        "bid_kind":    "사전규격",
        "bid_title":   pre_spec.prdct_clsfc_no_nm or "",
        "org_name":    pre_spec.order_instt_nm or "",
        "bid_date":    pre_spec.rcpt_dt.strftime("%Y-%m-%d %H:%M:%S") if pre_spec.rcpt_dt else "",
        "bid_clse_dt": pre_spec.opnin_rgst_clse_dt.strftime("%Y-%m-%d %H:%M:%S") if pre_spec.opnin_rgst_clse_dt else "",
        "budget":      str(pre_spec.asign_bdgt_amt or ""),
    })

    return doc_id


async def run_keyword_workflow(bid_title: str, rfp_text: str) -> list[str]:
    """
    Dify 키워드 추출 워크플로우 호출.
    입력: bid_title, rfp_text
    출력: keywords 리스트
    """
    headers = {
        "Authorization": f"Bearer {DIFY_KEYWORD_WORKFLOW_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {"bid_title": bid_title, "rfp_text": rfp_text},
        "response_mode": "blocking",
        "user": "bid-sync",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{DIFY_API_URL}/workflows/run",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    outputs = response.json().get("data", {}).get("outputs", {})

    keywords = outputs.get("keywords", [])
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.replace(",", "\n").splitlines() if k.strip()]

    logger.info(f"키워드 추출 완료: {len(keywords)}개")
    return keywords


async def run_reason_workflow(
    bid_title: str,
    bid_agency: str,
    bid_amount: str,
    service_type: str,
    matched_items: list[str],
    matched_keywords: list[str],
    rag_segment: str,
    match_score: float,
) -> str:
    """
    추천 이유 생성 Dify 워크플로우 호출.
    출력: reason (자연어 추천 이유 문자열)
    """
    headers = {
        "Authorization": f"Bearer {DIFY_REASON_WORKFLOW_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {
            "bid_title":        bid_title,
            "bid_agency":       bid_agency,
            "bid_amount":       bid_amount,
            "service_type":     service_type,
            "matched_items":    ", ".join(matched_items) if matched_items else "",
            "matched_keywords": ", ".join(matched_keywords) if matched_keywords else "",
            "rag_segment":      rag_segment,
            "match_score":      str(round(match_score * 100, 1)),
        },
        "response_mode": "blocking",
        "user": "bid-sync",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{DIFY_API_URL}/workflows/run",
            headers=headers,
            json=payload,
        )
        if not response.is_success:
            logger.error(f"추천이유 워크플로우 오류: {response.status_code} | {response.text[:500]}")
            response.raise_for_status()

    outputs = response.json().get("data", {}).get("outputs", {})
    reason = outputs.get("reason", "").strip()
    logger.debug(f"추천이유 생성 완료: {bid_title[:30]}...")
    return reason


async def update_pre_spec_metadata(doc_id: str, fields: dict) -> None:
    """사전규격 전용 지식DB 문서 메타데이터 업데이트."""
    await _update_metadata_for_dataset(DIFY_PRE_SPEC_DATASET_ID, doc_id, fields, PRE_SPEC_FIELD_IDS)


async def retrieve_pre_spec_rag_scores(query: str, doc_ids: list[str]) -> dict[str, dict]:
    """사전규격 전용 지식DB에서 RAG 점수 조회."""
    return await _retrieve_rag_scores_for_dataset(DIFY_PRE_SPEC_DATASET_ID, query, doc_ids)


async def _update_metadata_for_dataset(dataset_id: str, doc_id: str, fields: dict, field_ids: dict) -> None:
    """(내부) 특정 dataset의 문서 메타데이터 업데이트."""
    if not dataset_id:
        return

    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}

    metadata_list = [
        {"id": field_ids[key], "name": key, "value": value}
        for key, value in fields.items()
        if key in field_ids and field_ids[key]
    ]

    if not metadata_list:
        return

    payload = {
        "operation_data": [{
            "document_id": doc_id,
            "metadata_list": metadata_list,
            "partial_update": True,
        }]
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{DIFY_API_URL}/datasets/{dataset_id}/documents/metadata",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    logger.info(f"Dify 메타데이터 업데이트 완료: dataset={dataset_id} doc_id={doc_id}")


async def _retrieve_rag_scores_for_dataset(dataset_id: str, query: str, doc_ids: list[str]) -> dict[str, dict]:
    """(내부) 특정 dataset에서 RAG 점수 조회."""
    if not dataset_id or not doc_ids or not query.strip():
        return {}

    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "query": query,
        "retrieval_model": {
            "search_method": "semantic_search",
            "top_k": min(len(doc_ids) * 5, 2000),
            "score_threshold_enabled": False,
            "score_threshold": 0.0,
            "reranking_enable": False,
        },
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{DIFY_API_URL}/datasets/{dataset_id}/retrieve",
            headers=headers,
            json=payload,
        )
        if not response.is_success:
            logger.error(f"Dify retrieve 오류: {response.status_code} | {response.text[:500]}")
            response.raise_for_status()

    records = response.json().get("records", [])
    doc_id_set = set(doc_ids)

    results: dict[str, dict] = {}
    for record in records:
        segment = record.get("segment", {})
        doc_id = segment.get("document_id") or record.get("document", {}).get("id")
        score = float(record.get("score", 0.0))
        if doc_id in doc_id_set:
            if score > results.get(doc_id, {}).get("score", -1.0):
                content = (segment.get("content") or "").strip()
                results[doc_id] = {
                    "score": score,
                    "segment": content[:200] if content else "",
                }

    logger.info(f"RAG 검색 완료: {len(results)}/{len(doc_ids)}건 매칭")
    return results


async def update_metadata(doc_id: str, fields: dict) -> None:
    """입찰공고 지식DB 문서 메타데이터 업데이트."""
    await _update_metadata_for_dataset(DIFY_DATASET_ID, doc_id, fields, FIELD_IDS)


async def retrieve_rag_scores(query: str, doc_ids: list[str]) -> dict[str, dict]:
    """입찰공고 지식DB에서 RAG 점수 조회."""
    return await _retrieve_rag_scores_for_dataset(DIFY_DATASET_ID, query, doc_ids)