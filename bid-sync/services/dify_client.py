import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_DATASET_ID = os.getenv("DIFY_DATASET_ID", "")
DIFY_WORKFLOW_KEY = os.getenv("DIFY_WORKFLOW_KEY", "")

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


async def run_keyword_workflow(bid_title: str, rfp_text: str) -> list[str]:
    """
    Dify 키워드 추출 워크플로우 호출.
    입력: bid_title, rfp_text
    출력: keywords 리스트
    """
    headers = {
        "Authorization": f"Bearer {DIFY_WORKFLOW_KEY}",
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


async def update_metadata(doc_id: str, fields: dict) -> None:
    """
    Dify 문서 메타데이터 값 업데이트.
    fields: {"keywords": "...", ...}
    POST /datasets/{dataset_id}/documents/metadata
    """
    headers = {"Authorization": f"Bearer {DIFY_API_KEY}"}

    metadata_list = [
        {"id": FIELD_IDS[key], "name": key, "value": value}
        for key, value in fields.items()
        if key in FIELD_IDS and FIELD_IDS[key]
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
            f"{DIFY_API_URL}/datasets/{DIFY_DATASET_ID}/documents/metadata",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()

    logger.info(f"Dify 메타데이터 업데이트 완료: doc_id={doc_id}")