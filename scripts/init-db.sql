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

-- Diaries 테이블
CREATE TABLE IF NOT EXISTS diaries (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    diary_date TIMESTAMP WITH TIME ZONE NOT NULL,
    note TEXT,
    photo_count INTEGER NOT NULL DEFAULT 0,
    category VARCHAR(50) NOT NULL,
    tags TEXT[],
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

-- Diaries 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_diaries_user_id
    ON diaries(user_id);
CREATE INDEX IF NOT EXISTS idx_diaries_diary_date
    ON diaries(diary_date);
CREATE INDEX IF NOT EXISTS idx_diaries_deleted_at
    ON diaries(deleted_at);

-- Database 기본 설정 완료 메시지
DO $$
BEGIN
    RAISE NOTICE 'FoodDiary database initialized successfully!';
END $$;
