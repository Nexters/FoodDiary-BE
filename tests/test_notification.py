"""FCM 푸시 알림 통합 테스트"""

import os
from datetime import datetime, timezone

import pytest

from app.services.fcm_sender import send_notification


@pytest.mark.skipif(
    not os.getenv("TEST_FCM_TOKEN"),
    reason="TEST_FCM_TOKEN 환경변수가 설정되지 않았습니다. 실제 FCM 전송 테스트를 건너뜁니다.",
)
def test_fcm_integration_send_notification():
    """
    FCM 통합 테스트: 실제 FCM 알림 전송

    환경변수 설정 필요:
    - TEST_FCM_TOKEN: 실제 디바이스 FCM 토큰
    - FIREBASE_CREDENTIALS_JSON: Base64 인코딩된 서비스 계정 JSON
    """
    # Given: 실제 FCM 토큰
    test_fcm_token = os.getenv("TEST_FCM_TOKEN")

    # When: 실제 FCM 알림 전송 (notification + data)
    test_data = {
        "action": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": "FCM 통합 테스트",
    }

    result = send_notification(
        token=test_fcm_token,
        title="FoodDiary FCM 통합 테스트",
        body="이 메시지는 자동화된 테스트에서 전송되었습니다.",
        data=test_data,
    )

    # Then: 전송 성공
    assert result is True
