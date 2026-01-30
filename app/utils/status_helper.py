"""분석 상태 관리 헬퍼 함수"""

from app.models.diary import Diary
from app.models.photo import Photo


def get_analysis_status(photo: Photo) -> str:
    """
    사진의 분석 상태를 반환합니다.

    Args:
        photo: Photo 모델 인스턴스

    Returns:
        "pending" | "processing" | "done" | "failed"

    상태 정의:
    - pending: 분석 대기 중 (PhotoAnalysisResult 없음)
    - processing: 분석 진행 중 (PhotoAnalysisResult는 있지만 raw_response 없음)
    - done: 분석 완료 (raw_response 존재)
    - failed: 분석 실패 (추후 에러 처리 추가)
    """
    # PhotoAnalysisResult가 없으면 대기 중
    if not photo.analysis_result:
        return "pending"

    # raw_response가 없으면 진행 중
    if photo.analysis_result.raw_response is None:
        return "processing"

    # TODO: 에러 상태 처리 추가
    # if photo.analysis_result.error:
    #     return "failed"

    # raw_response가 있으면 완료
    return "done"


def get_diary_analysis_status(diary: Diary) -> str:
    """
    다이어리의 전체 분석 상태를 반환합니다.
    모든 사진이 분석 완료되어야 "done"

    Args:
        diary: Diary 모델 인스턴스 (photos가 eager load 되어야 함)

    Returns:
        "pending" | "processing" | "done" | "failed"

    상태 정의:
    - pending: 사진이 없거나 모두 대기 중
    - processing: 일부 사진이 분석 중
    - done: 모든 사진 분석 완료
    - failed: 하나 이상의 사진 분석 실패
    """
    # 사진이 없으면 대기 중
    if not diary.photos:
        return "pending"

    # 각 사진의 분석 상태 수집
    statuses = [get_analysis_status(photo) for photo in diary.photos]

    # 하나라도 실패하면 failed
    if any(status == "failed" for status in statuses):
        return "failed"

    # 모두 완료되면 done
    if all(status == "done" for status in statuses):
        return "done"

    # 하나라도 진행 중이면 processing
    if any(status == "processing" for status in statuses):
        return "processing"

    # 나머지는 pending
    return "pending"


def has_completed_analysis(diary: Diary) -> bool:
    """
    다이어리의 분석이 완료되었는지 확인합니다.

    Args:
        diary: Diary 모델 인스턴스

    Returns:
        분석 완료 여부
    """
    return get_diary_analysis_status(diary) == "done"


def needs_analysis(photo: Photo) -> bool:
    """
    사진이 분석이 필요한 상태인지 확인합니다.

    Args:
        photo: Photo 모델 인스턴스

    Returns:
        분석 필요 여부
    """
    status = get_analysis_status(photo)
    return status in ("pending", "failed")


def get_pending_photos(diary: Diary) -> list[Photo]:
    """
    다이어리에서 분석이 필요한 사진들을 반환합니다.

    Args:
        diary: Diary 모델 인스턴스

    Returns:
        분석 대기 중인 사진 리스트
    """
    return [photo for photo in diary.photos if needs_analysis(photo)]


def calculate_analysis_progress(diary: Diary) -> dict:
    """
    다이어리의 분석 진행률을 계산합니다.

    Args:
        diary: Diary 모델 인스턴스

    Returns:
        {
            "total": 전체 사진 수,
            "completed": 완료된 사진 수,
            "progress": 진행률 (0~100)
        }
    """
    if not diary.photos:
        return {
            "total": 0,
            "completed": 0,
            "progress": 0,
        }

    total = len(diary.photos)
    completed = sum(1 for photo in diary.photos if get_analysis_status(photo) == "done")
    progress = int((completed / total) * 100) if total > 0 else 0

    return {
        "total": total,
        "completed": completed,
        "progress": progress,
    }
