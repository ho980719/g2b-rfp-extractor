import shutil
import tempfile
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl
from starlette.background import BackgroundTask

from services.converter import validate_url, detect_file_info, download_file, run_libreoffice

logger = logging.getLogger(__name__)

router = APIRouter(tags=["convert"])


class ConvertRequest(BaseModel):
    url: HttpUrl


@router.post("/convert")
async def convert_to_pdf(request: ConvertRequest):
    url = str(request.url)
    validate_url(url)

    tmpdir = tempfile.mkdtemp()

    try:
        content, content_type, content_disposition = await download_file(url)

        result = detect_file_info(content_type, content_disposition, url)
        if result is None:
            shutil.rmtree(tmpdir, ignore_errors=True)
            return {"skipped": True, "reason": "지원하지 않는 파일 형식", "url": url}

        suffix, filename = result
        logger.info(f"변환 요청: {filename} ({suffix})")

        input_path = Path(tmpdir) / filename
        input_path.write_bytes(content)

        if suffix == ".pdf":
            return FileResponse(
                path=str(input_path),
                media_type="application/pdf",
                filename=filename,
                background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
            )

        output_path = await run_libreoffice(input_path, tmpdir)
        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=output_path.name,
            background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
        )

    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise
