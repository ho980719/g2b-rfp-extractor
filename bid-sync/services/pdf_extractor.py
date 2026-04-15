import logging
import os
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

MAX_CHARS = int(os.getenv("PDF_MAX_CHARS", 8000))


def extract_text(pdf_path: Path) -> str:
    """PDF에서 텍스트 추출 (MAX_CHARS 제한, 페이지별 오류 무시)"""
    texts = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.warning(f"PDF 열기 실패: {pdf_path.name} | {e}")
        return ""

    for i, page in enumerate(doc):
        try:
            text = page.get_text()
            if text and text.strip():
                texts.append(text.strip())
        except Exception as e:
            logger.debug(f"페이지 {i+1} 추출 실패 (무시): {e}")
            continue
        if sum(len(t) for t in texts) >= MAX_CHARS:
            break

    doc.close()

    full_text = "\n\n".join(texts)
    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS]

    logger.info(f"텍스트 추출 완료: {pdf_path.name} ({len(full_text)}자)")
    return full_text
