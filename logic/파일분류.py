import json


def main(api_result: str) -> dict:
    # RFP 판단 포함 키워드
    RFP_KEYWORDS = [
        "제안요청서", "rfp", "과업지시서", "과업내용서", "과업요청서",
        "규격서", "요구사항", "제안안내서", "사업수행계획",
        "기술규격", "과업범위", "업무범위", "기술제안", "수행계획",
        "사업내용", "과업설명서", "제안서작성", "기술사양"
    ]

    # RFP 제외 키워드
    EXCLUDE_KEYWORDS = [
        "입찰공고문", "유의사항", "계약서",
        "참가신청서", "서약서", "위임장"
    ]

    # 처리하지 않을 공고 종류
    SKIP_NTCE_KIND = ["취소공고", "낙찰공고", "유찰공고"]

    data = json.loads(api_result) if isinstance(api_result, str) else api_result
    items = data.get("response", {}).get("body", {}).get("items", [])

    if not items:
        return {
            "bids": [],
            "skipped": [],
            "rfp_found": False,
            "summary": "no results"
        }

    # 공고번호 기준 최신 차수만 남기기
    latest = {}
    for item in items:
        no = item.get("bidNtceNo", "")
        ord_ = item.get("bidNtceOrd", "000")
        if no not in latest or ord_ > latest[no].get("bidNtceOrd", "000"):
            latest[no] = item

    bids = []
    skipped = []

    for no, item in latest.items():
        ntce_kind = item.get("ntceKindNm", "")

        # 취소/낙찰/유찰 공고 스킵
        if ntce_kind in SKIP_NTCE_KIND:
            skipped.append({"bid_no": no, "reason": ntce_kind})
            continue

        # 첨부파일 추출 및 분류
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

            files.append({
                "index": i,
                "name": name,
                "url": file_url,
                "ext": ext,
                "file_type": file_type,
            })

        rfp_files = [f for f in files if f["file_type"] == "rfp"]
        unclear_files = [f for f in files if f["file_type"] == "unclear"]

        bids.append({
            "meta": {
                "bid_no": no,  # 공고번호
                "bid_ord": item.get("bidNtceOrd", ""),  # 차수
                "bid_kind": ntce_kind,  # 공고종류
                "bid_title": item.get("bidNtceNm", ""),  # 공고명
                "org_name": item.get("ntceInsttNm", ""),  # 기관명
                "bid_date": item.get("bidNtceDt", ""),  # 공고일
                "open_date": item.get("opengDt", ""),  # 개찰일
                "budget": item.get("asignBdgtAmt", ""),  # 추정금액
                "award_type": item.get("sucsfbidMthdNm", ""),  # 낙찰방법
                "detail_url": item.get("bidNtceDtlUrl", ""),  # 상세링크
            },
            "files": files,
            "rfp_files": rfp_files,
            "unclear_files": unclear_files,
            "has_rfp": len(rfp_files) > 0,
            "needs_llm": len(unclear_files) > 0 and len(rfp_files) == 0,
            "no_files": len(files) == 0,
        })

    summary_lines = []
    for b in bids:
        if b["has_rfp"]:
            status = f"RFP found: {b['rfp_files'][0]['name']}"
        elif b["needs_llm"]:
            status = f"LLM required: {[f['name'] for f in b['unclear_files']]}"
        else:
            status = "no files — check detail page"

        summary_lines.append(
            f"[{b['meta']['bid_title']}]\n"
            f"org: {b['meta']['org_name']} | open: {b['meta']['open_date']}\n"
            f"status: {status}"
        )

    return {
        "bids": bids,
        "skipped": skipped,
        "rfp_found": any(b["has_rfp"] for b in bids),
        "summary": "\n\n".join(summary_lines),
    }
