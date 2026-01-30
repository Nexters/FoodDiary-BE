"""EXIF 데이터 파싱 및 시간대 분류 유틸리티"""

from datetime import datetime

from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS


def extract_exif_data(image_file) -> dict:
    """
    이미지 파일에서 EXIF 데이터를 추출합니다.

    Args:
        image_file: UploadFile.file 또는 파일 경로

    Returns:
        {
            "taken_at": datetime | None,
            "latitude": float | None,
            "longitude": float | None
        }
    """
    try:
        # 파일 포인터를 처음으로 이동
        if hasattr(image_file, "seek"):
            image_file.seek(0)

        # PIL로 이미지 열기
        image = Image.open(image_file)

        # EXIF 데이터 추출
        exif_data = image._getexif()

        if not exif_data:
            return {
                "taken_at": None,
                "latitude": None,
                "longitude": None,
            }

        # 태그 이름으로 변환
        exif = {TAGS.get(tag, tag): value for tag, value in exif_data.items()}

        # 촬영 시각 추출
        taken_at = _extract_datetime(exif)

        # GPS 좌표 추출
        latitude, longitude = _extract_gps_coordinates(exif)

        return {
            "taken_at": taken_at,
            "latitude": latitude,
            "longitude": longitude,
        }

    except Exception as e:
        # EXIF 데이터가 없거나 파싱 실패 시
        print(f"EXIF 파싱 실패: {e}")
        return {
            "taken_at": None,
            "latitude": None,
            "longitude": None,
        }


def _extract_datetime(exif: dict) -> datetime | None:
    """EXIF에서 촬영 시각 추출"""
    # DateTimeOriginal이 가장 정확한 촬영 시각
    datetime_str = (
        exif.get("DateTimeOriginal")
        or exif.get("DateTime")
        or exif.get("DateTimeDigitized")
    )

    if not datetime_str:
        return None

    try:
        # EXIF 날짜 형식: "2024:01:29 12:34:56"
        return datetime.strptime(datetime_str, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None


def _extract_gps_coordinates(exif: dict) -> tuple[float | None, float | None]:
    """EXIF에서 GPS 좌표 추출"""
    gps_info = exif.get("GPSInfo")

    if not gps_info:
        return None, None

    try:
        # GPS 태그를 이름으로 변환
        gps_data = {GPSTAGS.get(tag, tag): value for tag, value in gps_info.items()}

        # 위도 추출
        lat_data = gps_data.get("GPSLatitude")
        lat_ref = gps_data.get("GPSLatitudeRef")

        # 경도 추출
        lon_data = gps_data.get("GPSLongitude")
        lon_ref = gps_data.get("GPSLongitudeRef")

        if not (lat_data and lon_data):
            return None, None

        # 도분초를 십진수로 변환
        latitude = convert_to_degrees(lat_data)
        longitude = convert_to_degrees(lon_data)

        # 방향 보정 (남위는 -, 서경은 -)
        if lat_ref == "S":
            latitude = -latitude
        if lon_ref == "W":
            longitude = -longitude

        return latitude, longitude

    except Exception as e:
        print(f"GPS 좌표 파싱 실패: {e}")
        return None, None


def convert_to_degrees(value: tuple) -> float:
    """
    GPS 좌표를 도분초(DMS)에서 십진수(Decimal)로 변환

    Args:
        value: (degrees, minutes, seconds) 튜플

    Returns:
        십진수 좌표

    Example:
        (37, 29, 54.6) -> 37.498500
    """
    degrees = float(value[0])
    minutes = float(value[1])
    seconds = float(value[2])

    return degrees + (minutes / 60.0) + (seconds / 3600.0)


def classify_time_type(taken_at: datetime | None) -> str:
    """
    촬영 시각을 기준으로 끼니를 분류합니다.

    Args:
        taken_at: 촬영 시각

    Returns:
        "breakfast" | "lunch" | "snack" | "dinner"

    분류 기준:
    - 05:00 ~ 10:59: breakfast (아침)
    - 11:00 ~ 14:59: lunch (점심)
    - 15:00 ~ 17:59: snack (간식)
    - 18:00 ~ 04:59: dinner (저녁)
    """
    if not taken_at:
        # EXIF 시간이 없으면 현재 시각 기준
        taken_at = datetime.now()

    hour = taken_at.hour

    if 5 <= hour < 11:
        return "breakfast"
    elif 11 <= hour < 15:
        return "lunch"
    elif 15 <= hour < 18:
        return "snack"
    else:  # 18 <= hour or hour < 5
        return "dinner"


def format_gps_to_point(latitude: float | None, longitude: float | None) -> str | None:
    """
    GPS 좌표를 PostgreSQL POINT 타입 문자열로 변환

    Args:
        latitude: 위도
        longitude: 경도

    Returns:
        "(longitude, latitude)" 형태의 문자열 또는 None

    Note:
        PostgreSQL POINT는 (x, y) = (경도, 위도) 순서입니다.
    """
    if latitude is None or longitude is None:
        return None

    return f"({longitude}, {latitude})"


def parse_point_to_gps(point_str: str | None) -> tuple[float | None, float | None]:
    """
    PostgreSQL POINT 타입 문자열을 GPS 좌표로 변환

    Args:
        point_str: "(longitude, latitude)" 형태의 문자열

    Returns:
        (latitude, longitude) 튜플
    """
    if not point_str:
        return None, None

    try:
        # "(127.027621, 37.497928)" -> "127.027621, 37.497928"
        coords = point_str.strip("()").split(",")
        longitude = float(coords[0].strip())
        latitude = float(coords[1].strip())
        return latitude, longitude
    except (ValueError, IndexError):
        return None, None
