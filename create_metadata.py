import requests

DATASET_ID = "866ffbd1-2f00-4e2d-b7d8-53b66287b7e8"
API_KEY = "dataset-fRqiIvN9daZYdA9QknRw7q63"
BASE = "https://llmops.misoinfo.co.kr/v1"

FIELDS = [
    "bid_no", "bid_ord", "bid_kind", "bid_title", "org_name",
    "bid_date", "open_date", "budget", "award_type", "detail_url",
    "bid_clse_dt", "keywords", "bid_clsfctn_no",
]

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

for name in FIELDS:
    res = requests.post(
        f"{BASE}/datasets/{DATASET_ID}/metadata",
        headers=headers,
        json={"type": "string", "name": name},
    )
    if res.ok:
        data = res.json()
        print(f"{name}: {data.get('id')}")
    else:
        print(f"{name}: 실패 {res.status_code} {res.text}")