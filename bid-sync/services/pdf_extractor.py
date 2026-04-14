import logging
import os
from pathlib import Path

import pdfplumber

logger = logging.getLogger(__name__)

MAX_CHARS = int(os.getenv("PDF_MAX_CHARS", 8000))


def extract_text(pdf_path: Path) -> str:
    """PDF에서 텍스트 추출 (MAX_CHARS 제한)"""
    texts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                texts.append(text.strip())
            if sum(len(t) for t in texts) >= MAX_CHARS:
                break

    full_text = "\n\n".join(texts)
    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS]

    logger.info(f"텍스트 추출 완료: {pdf_path.name} ({len(full_text)}자)")
    return full_text
