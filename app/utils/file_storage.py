"""파일 저장 유틸리티"""

import uuid
from pathlib import Path

from fastapi import UploadFile

UPLOAD_DIR = Path("data/photos")


async def save_uploaded_file(file: UploadFile) -> str:
    """
    업로드된 파일을 저장하고 URL을 반환합니다.

    Args:
        file: FastAPI UploadFile 객체

    Returns:
        str: 저장된 파일의 경로 (예: "data/photos/{uuid}.jpg")
    """
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 파일 확장자 추출
    filename = file.filename or "image.jpg"
    ext = Path(filename).suffix or ".jpg"

    # UUID 기반 고유 파일명 생성
    new_filename = f"{uuid.uuid4()}{ext}"
    filepath = UPLOAD_DIR / new_filename

    # 파일 저장
    content = await file.read()
    filepath.write_bytes(content)

    # 파일 포인터 리셋 (다른 곳에서 다시 읽을 수 있도록)
    await file.seek(0)

    return str(filepath)
