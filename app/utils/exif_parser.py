"""EXIF 데이터 파싱 유틸리티"""

from datetime import datetime
from typing import TypedDict

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


class ExifData(TypedDict):
    """EXIF 데이터 타입"""

    taken_at: datetime | None
    latitude: float | None
    longitude: float | None


def extract_exif_data(file) -> ExifData:
    """
    이미지 파일에서 EXIF 데이터를 추출합니다.

    Args:
        file: 파일 객체 (file-like object)

    Returns:
        ExifData: {
            "taken_at": datetime 또는 None,
            "latitude": float 또는 None,
            "longitude": float 또는 None
        }
    """
    result: ExifData = {
        "taken_at": None,
        "latitude": None,
        "longitude": None,
    }

    try:
        image = Image.open(file)
        exif_data = image._getexif()

        if exif_data is None:
            return result

        # EXIF 태그 파싱
        for tag_id, value in exif_data.items():
            tag = TAGS.get(tag_id, tag_id)

            # 촬영 시간
            if tag == "DateTimeOriginal":
                try:
                    result["taken_at"] = datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                except ValueError:
                    pass

            # GPS 정보
            if tag == "GPSInfo":
                gps_data = {}
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_data[gps_tag] = gps_value

                # 위도
                if "GPSLatitude" in gps_data and "GPSLatitudeRef" in gps_data:
                    lat = _convert_to_degrees(gps_data["GPSLatitude"])
                    if gps_data["GPSLatitudeRef"] == "S":
                        lat = -lat
                    result["latitude"] = lat

                # 경도
                if "GPSLongitude" in gps_data and "GPSLongitudeRef" in gps_data:
                    lng = _convert_to_degrees(gps_data["GPSLongitude"])
                    if gps_data["GPSLongitudeRef"] == "W":
                        lng = -lng
                    result["longitude"] = lng

    except Exception:
        pass  # EXIF 파싱 실패 시 기본값 반환

    return result


def _convert_to_degrees(value) -> float:
    """
    GPS 좌표를 도(degree) 단위로 변환합니다.

    Args:
        value: (degrees, minutes, seconds) 튜플

    Returns:
        float: 도 단위 좌표
    """
    d, m, s = value
    return float(d) + float(m) / 60 + float(s) / 3600
