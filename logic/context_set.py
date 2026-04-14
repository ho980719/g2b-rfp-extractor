def main(result: list) -> dict:

    context_blocks = []

    for item in result:
        meta = item.get("metadata", {}).get("doc_metadata", {})
        content = item.get("content", "")

        block = f"""
[공고 정보]
- 공고명: {meta.get('bid_title', '')}
- 공고번호: {meta.get('bid_no', '')}
- 발주기관: {meta.get('org_name', '')}
- 공고일: {meta.get('bid_date', '')}
- 개찰일: {meta.get('open_date', '')}
- 추정금액: {meta.get('budget', '')}원
- 낙찰방법: {meta.get('award_type', '')}
- 상세링크: {meta.get('detail_url', '')}

[상세 내용]
{content}
""".strip()

        context_blocks.append(block)

    return {
        "context": "\n\n---\n\n".join(context_blocks)
    }