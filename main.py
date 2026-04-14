from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
import asyncio
import tempfile
import shutil
import httpx
from pathlib import Path
from starlette.background import BackgroundTask
from urllib.parse import unquote, urlparse
import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()

LIBREOFFICE = "soffice"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_HOSTS = {"www.g2b.go.kr", "input.g2b.go.kr"}  # 필요 시 추가
CONVERT_TIMEOUT = 60.0  # 초


class ConvertRequest(BaseModel):
    url: HttpUrl


def validate_url(url: str):
    parsed = urlparse(url)
    if ALLOWED_HOSTS and parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=400, detail=f"허용되지 않는 도메인: {parsed.hostname}")

SUPPORTED_SUFFIXES = {".pdf", ".hwp", ".hwpx"}
SKIP_SUFFIXES = {
    ".zip", ".alz", ".rar", ".7z", ".tar", ".gz",  # 압축
    ".xls", ".xlsx", ".doc", ".docx", ".ppt", ".pptx",  # 오피스
    ".txt", ".csv", ".xml", ".json",  # 텍스트
    ".jpg", ".jpeg", ".png", ".gif",  # 이미지
}

def detect_file_info(content_type: str, content_disposition: str, url: str) -> tuple[str, str] | None:
    """
    (suffix, filename) 반환.
    스킵 대상이면 None 반환.
    판별 불가면 HTTPException.
    """
    # Content-Type 우선 판별
    if "pdf" in content_type:
        return ".pdf", "document.pdf"
    if "hwp" in content_type:
        return ".hwp", "document.hwp"
    if any(t in content_type for t in ("zip", "x-zip", "x-rar", "x-7z", "x-alz")):
        logger.info(f"스킵 (압축 content-type): {content_type}")
        return None

    # Content-Disposition 파일명 기반 판별
    if "filename=" in content_disposition:
        raw = content_disposition.split("filename=")[-1].strip().strip('"').rstrip(";")
        filename = unquote(raw)
        suffix = Path(filename).suffix.lower()
        if suffix in SUPPORTED_SUFFIXES:
            return suffix, filename
        if suffix:  # 확장자가 있는데 지원 안 하면 전부 스킵
            logger.info(f"스킵 (미지원 확장자): {filename}")
            return None

    # URL path 기반 fallback
    url_path = urlparse(url).path
    suffix = Path(url_path).suffix.lower()
    if suffix in SUPPORTED_SUFFIXES:
        return suffix, Path(url_path).name
    if suffix:
        logger.info(f"스킵 (URL 확장자): {suffix}")
        return None

    raise HTTPException(status_code=400, detail=f"파일 형식을 판별할 수 없음: {content_type}")


@app.post("/convert")
async def convert_to_pdf(request: ConvertRequest):
    url = str(request.url)
    validate_url(url)

    tmpdir = tempfile.mkdtemp()

    try:
        async with httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=5.0),
                follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        # 파일 크기 체크
        if len(response.content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="파일 크기 초과 (최대 50MB)")

        content_type = response.headers.get("content-type", "").lower()
        content_disposition = response.headers.get("content-disposition", "")

        result = detect_file_info(content_type, content_disposition, url)
        if result is None:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"skipped": True, "reason": "지원하지 않는 파일 형식", "url": url}

        suffix, filename = result

        logger.info(f"변환 요청: {filename} ({suffix})")

        input_path = Path(tmpdir) / filename

        with open(input_path, "wb") as f:
            f.write(response.content)

        # PDF는 그대로 반환
        if suffix == ".pdf":
            return FileResponse(
                path=str(input_path),
                media_type="application/pdf",
                filename=filename,
                background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True)
            )

        # LibreOffice 변환 (요청별 독립 프로파일)
        output_path = Path(tmpdir) / (Path(filename).stem + ".pdf")
        user_profile = Path(tmpdir) / "lo_profile"
        user_profile.mkdir()

        cmd = [
            LIBREOFFICE, "--headless",
            "--norestore",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{user_profile}",
            "--convert-to", "pdf",
            "--outdir", tmpdir,
            str(input_path)
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=CONVERT_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            raise HTTPException(status_code=504, detail="변환 타임아웃")

        if proc.returncode != 0 or not output_path.exists():
            logger.error(f"변환 실패: {filename} | {stderr.decode()}")
            raise HTTPException(status_code=500, detail=f"변환 실패: {stderr.decode()}")

        logger.info(f"변환 완료: {filename} -> {output_path.name}")
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=output_path.name,
            background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True)
        )

    except HTTPException:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
    except Exception as e:
        logger.error(f"처리 실패: {url} | {e}")
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}