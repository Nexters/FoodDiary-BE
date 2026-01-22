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
    email VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- Database 기본 설정 완료 메시지
DO $$
BEGIN
    RAISE NOTICE 'FoodDiary database initialized successfully!';
END $$;
