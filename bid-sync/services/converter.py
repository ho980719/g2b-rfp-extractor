import asyncio
import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

LIBREOFFICE = "soffice"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_HOSTS = {"www.g2b.go.kr", "input.g2b.go.kr"}
CONVERT_TIMEOUT = 60.0

SUPPORTED_SUFFIXES = {".pdf", ".hwp", ".hwpx"}
SKIP_SUFFIXES = {
    ".zip", ".alz", ".rar", ".7z", ".tar", ".gz",
    ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx",
    ".txt", ".csv", ".xml", ".json",
    ".jpg", ".jpeg", ".png", ".gif",
}


def validate_url(url: str):
    parsed = urlparse(url)
    if ALLOWED_HOSTS and parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 도메인: {parsed.hostname}")


def detect_file_info(content_type: str, content_disposition: str, url: str) -> tuple[str, str] | None:
    """
    (suffix, filename) 반환.
    스킵 대상이면 None 반환.
    판별 불가면 HTTPException.
    """
    if "pdf" in content_type:
        return ".pdf", "document.pdf"
    if "hwp" in content_type:
        return ".hwp", "document.hwp"
    if any(t in content_type for t in ("zip", "x-zip", "x-rar", "x-7z", "x-alz")):
        logger.info(f"스킵 (압축 content-type): {content_type}")
        return None

    if "filename=" in content_disposition:
        raw = content_disposition.split("filename=")[-1].strip().strip('"').rstrip(";")
        filename = unquote(raw)
        suffix = Path(filename).suffix.lower()
        if suffix in SUPPORTED_SUFFIXES:
            return suffix, filename
        if suffix:
            logger.info(f"스킵 (미지원 확장자): {filename}")
            return None

    url_path = urlparse(url).path
    suffix = Path(url_path).suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return suffix, Path(url_path).name
    if suffix:
        logger.info(f"스킵 (URL 확장자): {suffix}")
        return None

    raise HTTPException(status_code=400, detail=f"파일 형식을 판별할 수 없음: {content_type}")


async def download_file(url: str) -> tuple[bytes, str, str]:
    """(content, content_type, content_disposition) 반환"""
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30.0, connect=5.0),
        follow_redirects=True
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    if len(response.content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="파일 크기 초과 (최대 50MB)")

    return (
        response.content,
        response.headers.get("content-type", "").lower(),
        response.headers.get("content-disposition", ""),
    )


async def prepare_pdf(url: str, tmpdir: str) -> Path:
    """URL에서 파일을 받아 PDF Path 반환 (HWP/HWPX는 변환)"""
    content, content_type, content_disposition = await download_file(url)

    result = detect_file_info(content_type, content_disposition, url)
    if result is None:
        raise ValueError(f"지원하지 않는 파일 형식: {content_type}")

    suffix, filename = result
    input_path = Path(tmpdir) / filename
    input_path.write_bytes(content)

    if suffix == ".pdf":
        return input_path

    return await run_libreoffice(input_path, tmpdir)


async def run_libreoffice(input_path: Path, tmpdir: str) -> Path:
    """LibreOffice로 PDF 변환 후 output Path 반환"""
    output_path = Path(tmpdir) / (input_path.stem + ".pdf")
    user_profile = Path(tmpdir) / "lo_profile"
    user_profile.mkdir(exist_ok=True)

    cmd = [
        LIBREOFFICE, "--headless",
        "--norestore",
        "--nofirststartwizard",
        f"-env:UserInstallation=file://{user_profile}",
        "--convert-to", "pdf",
        "--outdir", tmpdir,
        str(input_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=CONVERT_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise HTTPException(status_code=504, detail="변환 타임아웃")

    if proc.returncode != 0 or not output_path.exists():
        logger.error(
            f"변환 실패: {input_path.name} | returncode={proc.returncode} "
            f"| stdout={stdout.decode(errors='replace')} "
            f"| stderr={stderr.decode(errors='replace')}"
        )
        raise HTTPException(status_code=500, detail=f"변환 실패: {stderr.decode(errors='replace')}")

    logger.info(f"변환 완료: {input_path.name} -> {output_path.name}")
    return output_path
