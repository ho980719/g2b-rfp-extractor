import json

def main(body: str, meta: dict) -> dict:

    # 1. body 파싱, document_id 추출
    parsed = json.loads(body)
    document_id = parsed["document"]["id"]

    # 2. field_id 매핑
    FIELD_IDS = {
        "bid_no":     "7bf5196d-2867-4b2e-ada3-41bb3ad852ed",
        "bid_ord":    "09860c77-a4d4-4255-852c-dbdbc889a622",
        "bid_kind":   "fd4d6ce3-1deb-48e9-9900-a9b4b1b9bdeb",
        "bid_title":  "9b9ecfe1-59d3-401a-82db-78a10bdcc97f",
        "org_name":   "3a283e9f-eca2-4879-8069-c6a1abe152bb",
        "bid_date":   "d06d0d22-1678-4b28-8932-a1efccde3d7c",
        "open_date":  "e7bf82d0-f23d-4e7d-87a0-73c6b8bdb40a",
        "budget":     "e543ca42-e956-4ea8-b973-448187a8f11f",
        "award_type": "cc43d5f2-8abb-48c8-8c86-fc05805831cb",
        "detail_url": "d40ef0a8-8144-40ca-851d-d8dc664fb47a",
    }

    # 3. metadata payload 구성
    metadata_list = [
        {"id": FIELD_IDS[key], "name": key, "value": str(val)}
        for key, val in meta.items()
        if key in FIELD_IDS
    ]

    payload = {
        "operation_data": [
            {
                "document_id": document_id,
                "metadata_list": metadata_list
            }
        ]
    }

    return {
        "document_id": document_id,
        "metadata_payload": json.dumps(payload, ensure_ascii=False)
    }