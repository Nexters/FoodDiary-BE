"""파일 저장 유틸리티 테스트"""

import shutil
from io import BytesIO
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import UploadFile

from app.utils.file_storage import STORAGE_DIR, save_file, save_user_photo


@pytest_asyncio.fixture
async def cleanup_storage():
    """테스트 전후 storage 디렉토리 정리"""
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)
    yield
    if STORAGE_DIR.exists():
        shutil.rmtree(STORAGE_DIR)


@pytest_asyncio.fixture
async def mock_upload_file():
    """Mock UploadFile 생성 헬퍼"""

    def create_mock_file(
        filename: str = "test_image.jpg", content: bytes = b"fake image content"
    ) -> UploadFile:
        file_obj = BytesIO(content)
        return UploadFile(filename=filename, file=file_obj)

    return create_mock_file


@pytest.mark.asyncio
async def test_save_user_photo_basic(mock_upload_file, cleanup_storage):
    """기본 저장 기능 및 디렉토리 구조 확인"""
    user_id = 1
    content = b"test image data"
    upload_file = mock_upload_file(content=content)

    filepath = await save_user_photo(user_id, upload_file)

    # 파일이 실제로 저장되었는지 확인
    assert Path(filepath).exists(), f"파일이 저장되지 않음: {filepath}"

    # 경로 구조 확인: storage/photos/1/xxx.jpg
    path_parts = Path(filepath).parts
    assert "storage" in path_parts
    assert "photos" in path_parts
    assert str(user_id) in path_parts

    # 내용 확인
    saved_content = Path(filepath).read_bytes()
    assert saved_content == content

    # 디렉토리 구조 출력 (디버깅용)
    print(f"\n✅ 저장된 파일: {filepath}")
    print("📁 디렉토리 구조:")
    for item in sorted(STORAGE_DIR.rglob("*")):
        print(f"  - {item.relative_to(STORAGE_DIR)}")


@pytest.mark.asyncio
async def test_save_user_photo_multiple_users(mock_upload_file, cleanup_storage):
    """여러 사용자의 파일이 각자 디렉토리에 저장되는지 확인"""
    user1_file = mock_upload_file(content=b"user1 photo")
    user2_file = mock_upload_file(content=b"user2 photo")

    filepath1 = await save_user_photo(1, user1_file)
    filepath2 = await save_user_photo(2, user2_file)

    # 각 사용자 디렉토리 확인
    assert Path(filepath1).exists()
    assert Path(filepath2).exists()
    assert "/1/" in filepath1
    assert "/2/" in filepath2

    # 디렉토리가 분리되어 있는지 확인
    user1_dir = STORAGE_DIR / "1"
    user2_dir = STORAGE_DIR / "2"
    assert user1_dir.exists()
    assert user2_dir.exists()

    print(f"\n✅ User 1 파일: {filepath1}")
    print(f"✅ User 2 파일: {filepath2}")
    print("📁 디렉토리 구조:")
    for item in sorted(STORAGE_DIR.rglob("*")):
        print(f"  - {item.relative_to(STORAGE_DIR)}")


@pytest.mark.asyncio
async def test_save_user_photo_multiple_files_same_user(
    mock_upload_file, cleanup_storage
):
    """같은 사용자가 여러 파일을 저장할 때 고유한 파일명 생성 확인"""
    user_id = 1
    file1 = mock_upload_file(filename="photo.jpg", content=b"photo1")
    file2 = mock_upload_file(filename="photo.jpg", content=b"photo2")
    file3 = mock_upload_file(filename="photo.jpg", content=b"photo3")

    filepath1 = await save_user_photo(user_id, file1)
    filepath2 = await save_user_photo(user_id, file2)
    filepath3 = await save_user_photo(user_id, file3)

    # 모든 파일이 존재하고 고유한지 확인
    assert Path(filepath1).exists()
    assert Path(filepath2).exists()
    assert Path(filepath3).exists()
    assert filepath1 != filepath2 != filepath3

    # 내용이 각각 다른지 확인
    assert Path(filepath1).read_bytes() == b"photo1"
    assert Path(filepath2).read_bytes() == b"photo2"
    assert Path(filepath3).read_bytes() == b"photo3"

    print(f"\n✅ 파일 1: {Path(filepath1).name}")
    print(f"✅ 파일 2: {Path(filepath2).name}")
    print(f"✅ 파일 3: {Path(filepath3).name}")


@pytest.mark.asyncio
async def test_save_user_photo_preserves_extension(mock_upload_file, cleanup_storage):
    """파일 확장자가 유지되는지 확인"""
    user_id = 1

    jpg_file = mock_upload_file(filename="test.jpg")
    png_file = mock_upload_file(filename="test.png")
    gif_file = mock_upload_file(filename="test.gif")

    jpg_path = await save_user_photo(user_id, jpg_file)
    png_path = await save_user_photo(user_id, png_file)
    gif_path = await save_user_photo(user_id, gif_file)

    assert jpg_path.endswith(".jpg")
    assert png_path.endswith(".png")
    assert gif_path.endswith(".gif")


@pytest.mark.asyncio
async def test_save_user_photo_handles_no_extension(mock_upload_file, cleanup_storage):
    """확장자가 없는 파일명에 .jpg 기본값 적용"""
    user_id = 1
    upload_file = mock_upload_file(filename="noextension")

    filepath = await save_user_photo(user_id, upload_file)

    assert filepath.endswith(".jpg")
    assert Path(filepath).exists()


@pytest.mark.asyncio
async def test_save_user_photo_handles_none_filename(mock_upload_file, cleanup_storage):
    """filename이 None일 때 기본값 적용"""
    user_id = 1
    file_obj = BytesIO(b"content")
    upload_file = UploadFile(filename=None, file=file_obj)

    filepath = await save_user_photo(user_id, upload_file)

    assert filepath.endswith(".jpg")
    assert Path(filepath).exists()


@pytest.mark.asyncio
async def test_save_user_photo_resets_file_pointer(mock_upload_file, cleanup_storage):
    """파일 포인터가 리셋되어 재사용 가능한지 확인"""
    user_id = 1
    content = b"test content"
    upload_file = mock_upload_file(content=content)

    await save_user_photo(user_id, upload_file)

    # 파일 포인터가 리셋되어 다시 읽을 수 있어야 함
    reread_content = await upload_file.read()
    assert reread_content == content


def test_save_file_basic(cleanup_storage):
    """save_file 기본 동작 확인"""
    filepath = STORAGE_DIR / "test_dir" / "test.txt"
    content = b"test content"

    result = save_file(filepath, content)

    assert Path(result).exists()
    assert Path(result).read_bytes() == content
    assert Path(result).parent.exists()


def test_save_file_with_string_path(cleanup_storage):
    """문자열 경로 처리 확인"""
    filepath = str(STORAGE_DIR / "test_dir" / "test.txt")
    content = b"test content"

    result = save_file(filepath, content)

    assert Path(result).exists()
    assert Path(result).read_bytes() == content


def test_save_file_creates_nested_directories(cleanup_storage):
    """중첩된 디렉토리 자동 생성 확인"""
    filepath = STORAGE_DIR / "a" / "b" / "c" / "test.txt"
    content = b"nested content"

    result = save_file(filepath, content)

    assert Path(result).exists()
    assert Path(result).read_bytes() == content


def test_save_file_overwrites_existing(cleanup_storage):
    """기존 파일 덮어쓰기 확인"""
    filepath = STORAGE_DIR / "test.txt"
    old_content = b"old"
    new_content = b"new"

    save_file(filepath, old_content)
    save_file(filepath, new_content)

    assert Path(filepath).read_bytes() == new_content
