-- ======================
-- FoodDiary Database Initialization
-- ======================
-- PostgreSQL 데이터베이스 초기 설정 스크립트

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone
SET timezone = 'Asia/Seoul';

-- Create custom types (필요시 추가)
-- Example: CREATE TYPE status_type AS ENUM ('active', 'inactive');

-- ======================
-- Create Tables
-- ======================

-- Users 테이블
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(10) NOT NULL,
    provider_user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,

    CONSTRAINT unique_provider_user UNIQUE (provider, provider_user_id)
);

-- Users 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_users_provider_user_id
    ON users(provider, provider_user_id);


-- ======================
-- Diaries 테이블
-- ======================
-- 끼니별 하나의 일기 (특정 날짜 + 유저 + 메모)
CREATE TABLE IF NOT EXISTS diaries (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    diary_date TIMESTAMP WITH TIME ZONE NOT NULL,
    time_type VARCHAR(20) NOT NULL CHECK (time_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
    restaurant_name VARCHAR(255),
    category VARCHAR(100),
    place_url VARCHAR(500),
    cover_photo_id INTEGER,
    note TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    photo_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    
    CONSTRAINT unique_user_date_time UNIQUE (user_id, diary_date, time_type)
);

-- Diaries 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_diaries_user_date 
    ON diaries(user_id, diary_date DESC);
CREATE INDEX IF NOT EXISTS idx_diaries_user_id 
    ON diaries(user_id);

-- Diaries 테이블 컬럼 설명
COMMENT ON COLUMN diaries.place_url IS '장소 URL (예: 카카오맵 링크 https://place.map.kakao.com/xxxxx)';

-- ======================
-- DiaryAnalysis 테이블
-- ======================
-- 다이어리 하나에 대한 AI 추론 결과 (유저 미확정 상태)
CREATE TABLE IF NOT EXISTS diary_analysis (
    diary_id INTEGER PRIMARY KEY REFERENCES diaries(id) ON DELETE CASCADE,
    restaurant_candidates JSONB DEFAULT '[]'::jsonb,
    category_candidates JSONB DEFAULT '[]'::jsonb,
    menu_candidates JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ======================
-- Photos 테이블
-- ======================
-- 업로드한 사진 하나 = 하나의 Photo 레코드
CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    diary_id INTEGER NOT NULL REFERENCES diaries(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    taken_at TIMESTAMP,
    taken_location VARCHAR(100),  -- "latitude,longitude" 형식 (예: "37.5186,126.9305")
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Photos 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_photos_diary_id 
    ON photos(diary_id);
CREATE INDEX IF NOT EXISTS idx_photos_taken_at 
    ON photos(taken_at DESC);

-- ======================
-- PhotoAnalysisResult 테이블
-- ======================
-- 사진 하나에 대한 AI 추론 결과 (유저 미확정 상태)
CREATE TABLE IF NOT EXISTS photo_analysis_results (
    id SERIAL PRIMARY KEY,
    photo_id INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    food_category VARCHAR(100),
    restaurant_name_candidates JSONB DEFAULT '[]'::jsonb,
    menu_candidates JSONB DEFAULT '[]'::jsonb,
    keywords JSONB DEFAULT '[]'::jsonb,
    raw_response TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_photo_analysis UNIQUE (photo_id)
);

-- PhotoAnalysisResult 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_photo_analysis_photo_id 
    ON photo_analysis_results(photo_id);

-- ======================
-- Devices 테이블
-- ======================
-- 푸시 알림을 위한 디바이스 정보
CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT False,
    device_token VARCHAR(255),
    app_version VARCHAR(20) NOT NULL,
    os_version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- Devices 테이블 인덱스
CREATE UNIQUE INDEX IF NOT EXISTS idx_device_device_id 
    ON devices(device_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_device_user_id
    ON devices(user_id);

-- ======================
-- Foreign Key 업데이트
-- ======================
-- diaries 테이블의 cover_photo_id에 대한 외래 키 제약 조건 추가
ALTER TABLE diaries 
    ADD CONSTRAINT fk_diaries_cover_photo 
    FOREIGN KEY (cover_photo_id) 
    REFERENCES photos(id) 
    ON DELETE SET NULL;

-- ======================
-- Trigger 함수 생성
-- ======================
-- updated_at 자동 업데이트 트리거 함수
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 각 테이블에 updated_at 자동 업데이트 트리거 적용
CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON users 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_diaries_updated_at 
    BEFORE UPDATE ON diaries 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_photos_updated_at 
    BEFORE UPDATE ON photos 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_photo_analysis_results_updated_at
    BEFORE UPDATE ON photo_analysis_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_devices_updated_at
    BEFORE UPDATE ON devices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- Database 기본 설정 완료 메시지
DO $$
BEGIN
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'FoodDiary database initialized successfully!';
    RAISE NOTICE '==============================================';
    RAISE NOTICE 'Created tables:';
    RAISE NOTICE '  - users';
    RAISE NOTICE '  - diaries';
    RAISE NOTICE '  - diary_analysis';
    RAISE NOTICE '  - photos';
    RAISE NOTICE '  - photo_analysis_results';
    RAISE NOTICE '  - devices';
    RAISE NOTICE '==============================================';
END $$;
