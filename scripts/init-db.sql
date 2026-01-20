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

-- Database 기본 설정 완료 메시지
DO $$
BEGIN
    RAISE NOTICE 'FoodDiary database initialized successfully!';
END $$;
