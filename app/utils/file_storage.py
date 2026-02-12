"""파일 저장 유틸리티"""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

STORAGE_DIR = Path("storage/photos")


async def save_user_photo(user_id: UUID, file: UploadFile) -> str:
    """
    사용자별 디렉토리에 사진을 저장합니다.

    Args:
        user_id: 사용자 ID
        file: FastAPI UploadFile 객체

    Returns:
        str: 저장된 파일의 경로 (예: "storage/photos/{user_id}/{uuid}.jpg")
    """
    filename = file.filename or "image.jpg"
    ext = Path(filename).suffix or ".jpg"
    new_filename = f"{uuid4()}{ext}"

    user_dir = STORAGE_DIR / str(user_id)
    filepath = user_dir / new_filename

    content = await file.read()
    await file.seek(0)

    return save_file(filepath, content)


def save_file(filepath: Path | str, content: bytes) -> str:
    """
    파일을 지정된 경로에 저장합니다.

    Args:
        filepath: 저장할 파일의 전체 경로
        content: 파일 내용

    Returns:
        str: 저장된 파일의 경로
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    return str(path)
