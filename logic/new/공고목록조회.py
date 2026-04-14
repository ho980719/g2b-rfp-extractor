import requests
import datetime
import json
import math

SERVICE_KEY = "8kD4C3UuAyTzdzHAZWWCuLHHf%2BOohV9QydQYRaGY5q3E%2FlZNg8%2BO4vCNf0o6IGfw0Y1iD6RGZ53kB6rHrgHnuA%3D%3D"
BASE_URL = "http://apis.data.go.kr/1230000/ad/BidPublicInfoService/getBidPblancListInfoServcPPSSrch"

logs = []


def get_bids_page(start_dt: str, end_dt: str, num_of_rows: int, page_no: int) -> dict | None:
    url = (
        f"{BASE_URL}"
        f"?serviceKey={SERVICE_KEY}"
        f"&pageNo={page_no}"
        f"&numOfRows={num_of_rows}"
        f"&inqryDiv=1"
        f"&type=json"
        f"&inqryBgnDt={start_dt}"
        f"&inqryEndDt={end_dt}"
    )

    safe_url = url.split("serviceKey")[0]
    logs.append(f"[요청] page={page_no} | {start_dt} ~ {end_dt}")

    try:
        response = requests.get(url, timeout=15)
        logs.append(f"[응답] status={response.status_code}")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logs.append(f"[오류] {str(e)}")
        return None


def extract_items(raw_data: dict) -> list:
    try:
        items = raw_data["response"]["body"]["items"]
        if isinstance(items, dict):
            item = items.get("item", [])
            return [item] if isinstance(item, dict) else (item or [])
        elif isinstance(items, list):
            return items
        return []
    except Exception:
        return []


def get_total_count(raw_data: dict) -> int:
    try:
        return int(raw_data["response"]["body"]["totalCount"])
    except Exception:
        return 0


def main() -> dict:
    global logs
    logs = []  # 실행마다 초기화

    interval_minutes = 10

    # now = datetime.datetime.now()
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=9) # KST 기준으로 변경

    floored = now.replace(
        minute=(now.minute // interval_minutes) * interval_minutes,
        second=0,
        microsecond=0
    )
    start_dt = floored - datetime.timedelta(minutes=interval_minutes)
    end_dt = floored

    start_str = start_dt.strftime("%Y%m%d%H%M")
    end_str = end_dt.strftime("%Y%m%d%H%M")

    logs.append(f"[시작] 실행시각={now.strftime('%Y-%m-%d %H:%M:%S')} | 조회구간={start_str} ~ {end_str}")

    # 1페이지로 totalCount 먼저 파악
    first_page = get_bids_page(start_str, end_str, num_of_rows=100, page_no=1)

    header = first_page.get("response", {}).get("header", {}) if first_page else {"resultCode": "99", "resultMsg": "NO DATA"}
    all_items = extract_items(first_page) if first_page else []

    # 전체 페이지 순회
    total_count = 0
    if first_page:
        total_count = get_total_count(first_page)
        logs.append(f"[totalCount] {total_count}건")

        if total_count > 100:
            total_pages = math.ceil(total_count / 100)
            logs.append(f"[페이징] 총 {total_pages}페이지 순회 시작")

            for page_no in range(2, total_pages + 1):
                page_data = get_bids_page(start_str, end_str, num_of_rows=100, page_no=page_no)
                if not page_data:
                    logs.append(f"[페이징 중단] page={page_no} 응답 없음")
                    break
                items = extract_items(page_data)
                all_items.extend(items)
                logs.append(f"[페이징] page={page_no} | 수집={len(items)}건 | 누적={len(all_items)}건")

    # 게시일시 내림차순 정렬
    all_items.sort(key=lambda x: x.get("bidNtceDt", ""), reverse=True)
    logs.append(f"[정렬 완료] 최종 수집={len(all_items)}건")

    # 400,000자 제한 이진 탐색
    lo, hi = 0, len(all_items)
    result_str = json.dumps({"response": {"header": header, "body": {"items": []}}}, ensure_ascii=False)

    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = json.dumps(
            {"response": {"header": header, "body": {"items": all_items[:mid]}}},
            ensure_ascii=False
        )
        if len(candidate) < 400000:
            result_str = candidate
            lo = mid
        else:
            hi = mid - 1

    parsed = json.loads(result_str)
    items_only = parsed.get("response", {}).get("body", {}).get("items", [])

    truncated = lo < len(all_items)
    logs.append(f"[출력] {lo}건 반환 | truncated={truncated}")

    return {
        "result": result_str,
        "items_json": json.dumps(items_only, ensure_ascii=False),  # sync용
        "debug": json.dumps({
            "logs": logs,
            "range_start": start_str,
            "range_end": end_str,
            "total_count": total_count,
            "fetched_count": len(all_items),
            "returned_count": lo,
            "truncated": truncated,
        }, ensure_ascii=False)
    }