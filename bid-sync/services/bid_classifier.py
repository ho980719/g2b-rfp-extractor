RFP_KEYWORDS = [
    "제안요청서", "rfp", "과업지시서", "과업내용서", "과업요청서",
    "규격서", "요구사항", "제안안내서", "사업수행계획",
    "기술규격", "과업범위", "업무범위", "기술제안", "수행계획",
    "사업내용", "과업설명서", "제안서작성", "기술사양"
]
EXCLUDE_KEYWORDS = ["입찰공고문", "유의사항", "계약서", "참가신청서", "서약서", "위임장"]
SKIP_NTCE_KIND = {"취소공고", "낙찰공고", "유찰공고"}


def extract_files(item: dict) -> list[dict]:
    files = []
    for i in range(1, 11):
        suffix = "" if i == 1 else str(i)
        name = item.get(f"ntceSpecFileNm{suffix}", "").strip()
        file_url = item.get(f"ntceSpecDocUrl{suffix}", "").strip()
        if not name or not file_url:
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else "unknown"
        name_lower = name.lower()
        if any(kw in name_lower for kw in EXCLUDE_KEYWORDS):
            file_type = "exclude"
        elif any(kw in name_lower for kw in RFP_KEYWORDS):
            file_type = "rfp"
        else:
            file_type = "unclear"
        files.append({"index": i, "name": name, "url": file_url, "ext": ext, "file_type": file_type})
    return files


def pick_rfp_target(files: list[dict]) -> dict | None:
    """PDF 우선, 없으면 첫 번째 RFP 파일"""
    rfp_files = [f for f in files if f["file_type"] == "rfp"]
    return (
        next((f for f in rfp_files if f["ext"] == "pdf"), None)
        or (rfp_files[0] if rfp_files else None)
    )


def classify_bid(item: dict) -> dict | None:
    """취소/낙찰/유찰 공고면 None 반환"""
    if item.get("ntceKindNm") in SKIP_NTCE_KIND:
        return None
    files = extract_files(item)
    target = pick_rfp_target(files)
    rfp_files = [f for f in files if f["file_type"] == "rfp"]
    unclear_files = [f for f in files if f["file_type"] == "unclear"]
    return {
        "has_rfp": bool(target),
        "needs_llm": len(unclear_files) > 0 and not rfp_files,
        "rfp_url": target["url"] if target else None,
        "rfp_name": target["name"] if target else None,
        "rfp_ext": target["ext"] if target else None,
        "file_urls": [f["url"] for f in files],
    }
