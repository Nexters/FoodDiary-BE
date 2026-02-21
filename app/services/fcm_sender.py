"""FCM 푸시 알림 서비스"""

import base64
import dataclasses
import json
import logging

import firebase_admin
from firebase_admin import credentials, messaging
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


def send_notification(
    token: str,
    title: str,
    body: str,
    data: object | None = None,
) -> bool:
    """FCM 토큰으로 직접 푸시 알림 전송.

    Args:
        token: FCM 디바이스 토큰
        title: 알림 제목
        body: 알림 본문
        data: 추가 데이터 페이로드 (어떤 객체든 허용, 선택)

    Returns:
        전송 성공 여부
    """
    if not token:
        logger.warning("FCM 토큰 없음")
        return False

    fcm_data = _serialize_data(data) if data is not None else None

    message = messaging.Message(
        notification=messaging.Notification(title=title, body=body),
        data=fcm_data,
        token=token,
    )

    try:
        messaging.send(message)
        logger.info("FCM 전송 성공: title=%s, body=%s", title, body)
        return True
    except messaging.UnregisteredError:
        logger.warning("만료된 FCM 토큰: token=%s", token[:20])
        return False
    except messaging.SenderIdMismatchError:
        logger.warning("Sender ID 불일치: token=%s", token[:20])
        return False
    except ValueError as e:
        logger.error("잘못된 FCM 인자: error=%s", e)
        return False
    except Exception:
        logger.exception("FCM 전송 실패")
        return False


def send_silent_push(token: str, data: object) -> bool:
    """FCM 토큰으로 Silent Push (data-only) 전송.

    사용자에게 알림을 표시하지 않고 백그라운드로 데이터만 전송합니다.
    앱이 백그라운드에서 데이터를 받아 처리할 수 있습니다.

    Args:
        token: FCM 디바이스 토큰
        data: 전송할 데이터 페이로드 (어떤 객체든 허용)

    Returns:
        전송 성공 여부
    """
    if not token:
        logger.warning("FCM 토큰 없음")
        return False

    if data is None:
        logger.warning("Silent push에는 data 필수")
        return False

    fcm_data = _serialize_data(data)
    logger.info("FCM Silent Push 전송 시도: data=%s, token=%s...", fcm_data, token[:20])

    message = messaging.Message(
        data=fcm_data,
        token=token,
    )

    try:
        message_id = messaging.send(message)
        logger.info("FCM Silent Push 전송 성공: message_id=%s", message_id)
        return True
    except messaging.UnregisteredError:
        logger.warning("만료된 FCM 토큰: token=%s...", token[:20])
        return False
    except messaging.SenderIdMismatchError:
        logger.warning("Sender ID 불일치: token=%s...", token[:20])
        return False
    except ValueError as e:
        logger.error("잘못된 FCM 인자: error=%s", e)
        return False
    except Exception:
        logger.exception("FCM Silent Push 전송 실패: token=%s...", token[:20])
        return False


def _serialize_data(data: object) -> dict[str, str]:
    """임의 객체를 FCM data payload(dict[str, str])로 변환."""
    if isinstance(data, dict):
        raw = data
    elif isinstance(data, BaseModel):
        raw = data.model_dump()
    elif dataclasses.is_dataclass(data) and not isinstance(data, type):
        raw = dataclasses.asdict(data)
    else:
        raw = vars(data)

    return {str(k): str(v) for k, v in raw.items()}


def initialize_firebase() -> None:
    """Firebase Admin SDK 초기화. Base64 인코딩된 credentials JSON을 디코딩하여 사용."""
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    if not settings.FIREBASE_CREDENTIALS_JSON:
        logger.warning("FIREBASE_CREDENTIALS_JSON 미설정, FCM 비활성")
        return

    try:
        decoded = base64.b64decode(settings.FIREBASE_CREDENTIALS_JSON)
        service_account = json.loads(decoded)
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK 초기화 완료")
    except Exception:
        logger.exception("Firebase Admin SDK 초기화 실패")
