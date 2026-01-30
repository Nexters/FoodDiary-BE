"""파일 저장 및 관리 유틸리티"""

import shutil
import uuid
from pathlib import Path

from fastapi import UploadFile


async def save_uploaded_file(file: UploadFile, base_dir: str = "data/photos") -> str:
    """
    업로드된 파일을 로컬 디스크에 저장합니다.

    Args:
        file: FastAPI UploadFile 객체
        base_dir: 저장할 기본 디렉토리

    Returns:
        저장된 파일의 URL (또는 경로)

    Note:
        추후 S3/CloudFlare 스토리지로 전환 가능
    """
    # 저장 디렉토리 생성
    storage_path = Path(base_dir)
    storage_path.mkdir(parents=True, exist_ok=True)

    # 고유한 파일명 생성
    filename = generate_filename(file.filename or "image.jpg")
    file_path = storage_path / filename

    # 파일 저장
    try:
        # 파일 포인터를 처음으로 이동
        await file.seek(0)

        # 파일 저장 (비동기)
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # URL 반환 (로컬 개발 환경)
        # 실제 서비스에서는 CDN URL 또는 full URL 반환
        return f"/static/photos/{filename}"

    except Exception as e:
        raise OSError(f"파일 저장 실패: {e}")


def generate_filename(original_filename: str) -> str:
    """
    고유한 파일명을 생성합니다.

    Args:
        original_filename: 원본 파일명

    Returns:
        UUID 기반의 고유한 파일명

    Example:
        "photo.jpg" -> "550e8400-e29b-41d4-a716-446655440000.jpg"
    """
    # 파일 확장자 추출
    ext = Path(original_filename).suffix

    # 확장자가 없으면 기본값
    if not ext:
        ext = ".jpg"

    # UUID로 고유한 파일명 생성
    return f"{uuid.uuid4()}{ext}"


def delete_file(file_url: str, base_dir: str = "data/photos") -> bool:
    """
    저장된 파일을 삭제합니다.

    Args:
        file_url: 파일 URL (예: "/static/photos/xxx.jpg")
        base_dir: 저장 디렉토리

    Returns:
        삭제 성공 여부
    """
    try:
        # URL에서 파일명 추출
        filename = Path(file_url).name
        file_path = Path(base_dir) / filename

        if file_path.exists():
            file_path.unlink()
            return True
        return False

    except Exception as e:
        print(f"파일 삭제 실패: {e}")
        return False


def get_file_size(file: UploadFile) -> int:
    """
    업로드 파일의 크기를 바이트 단위로 반환합니다.

    Args:
        file: FastAPI UploadFile 객체

    Returns:
        파일 크기 (bytes)
    """
    # 파일 끝으로 이동
    file.file.seek(0, 2)
    size = file.file.tell()

    # 파일 포인터를 처음으로 이동
    file.file.seek(0)

    return size


def validate_image_file(file: UploadFile, max_size_mb: int = 10) -> tuple[bool, str]:
    """
    이미지 파일의 유효성을 검증합니다.

    Args:
        file: FastAPI UploadFile 객체
        max_size_mb: 최대 파일 크기 (MB)

    Returns:
        (유효 여부, 에러 메시지)
    """
    # Content-Type 검증
    if not file.content_type or not file.content_type.startswith("image/"):
        return False, f"이미지 파일만 업로드 가능합니다. (현재: {file.content_type})"

    # 파일 크기 검증
    file_size = get_file_size(file)
    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        size_mb = file_size / (1024 * 1024)
        return (
            False,
            f"파일 크기는 {max_size_mb}MB를 초과할 수 없습니다. (현재: {size_mb:.2f}MB)",
        )

    # 파일 확장자 검증
    allowed_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic"}
    ext = Path(file.filename or "").suffix.lower()

    if ext not in allowed_extensions:
        return False, f"지원하지 않는 파일 형식입니다. (현재: {ext})"

    return True, ""


# S3 업로드 함수 (추후 구현)
async def upload_to_s3(file: UploadFile, bucket: str, key: str) -> str:
    """
    파일을 AWS S3에 업로드합니다.

    Args:
        file: FastAPI UploadFile 객체
        bucket: S3 버킷 이름
        key: S3 객체 키

    Returns:
        S3 URL

    Note:
        추후 boto3를 사용하여 구현
    """
    # TODO: boto3를 사용한 S3 업로드 구현
    raise NotImplementedError("S3 업로드는 추후 구현 예정입니다.")
