-- ============================================================================
-- CareCloud Voice AI Agent - Patient Registration System Database Schema
-- Database: PostgreSQL (Supabase)
-- ============================================================================

-- Enable UUID extension if not already active (standard on Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Create Patient Sex Enum
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'patient_sex') THEN
        CREATE TYPE patient_sex AS ENUM ('Male', 'Female', 'Other', 'Decline to Answer');
    END IF;
END $$;

-- 2. Create Patients Table
CREATE TABLE IF NOT EXISTS patients (
    patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Required Demographic Fields
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    sex patient_sex NOT NULL,
    phone_number VARCHAR(20) NOT NULL,
    
    -- Address Fields
    address_line_1 VARCHAR(255) NOT NULL,
    address_line_2 VARCHAR(100),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL,
    zip_code VARCHAR(10) NOT NULL,
    
    -- Optional Demographic & Insurance Fields
    email VARCHAR(255),
    insurance_provider VARCHAR(100),
    insurance_member_id VARCHAR(100),
    preferred_language VARCHAR(50) DEFAULT 'English',
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    
    -- Audit & Soft-Delete Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    deleted_at TIMESTAMPTZ, -- Soft-delete: NULL = active, timestamp = deleted

    -- Constraints enforcing CareCloud business validation rules
    CONSTRAINT check_first_name_format CHECK (first_name ~ '^[A-Za-z''\-\s]{1,50}$'),
    CONSTRAINT check_last_name_format CHECK (last_name ~ '^[A-Za-z''\-\s]{1,50}$'),
    CONSTRAINT check_dob_not_future CHECK (date_of_birth <= CURRENT_DATE),
    CONSTRAINT check_state_code CHECK (state ~ '^[A-Z]{2}$'),
    CONSTRAINT check_zip_format CHECK (zip_code ~ '^\d{5}(-\d{4})?$')
);

-- 3. Optimized Indexes for High-Speed API Querying & Duplicate Detection
-- Query index for GET /patients?last_name=...
CREATE INDEX IF NOT EXISTS idx_patients_last_name ON patients(last_name) WHERE deleted_at IS NULL;

-- Query index for GET /patients?date_of_birth=...
CREATE INDEX IF NOT EXISTS idx_patients_dob ON patients(date_of_birth) WHERE deleted_at IS NULL;

-- Fast index for duplicate phone detection during incoming phone calls
CREATE INDEX IF NOT EXISTS idx_patients_phone_number ON patients(phone_number) WHERE deleted_at IS NULL;

-- Primary active-filter index for soft delete queries
CREATE INDEX IF NOT EXISTS idx_patients_active ON patients(patient_id) WHERE deleted_at IS NULL;

-- 4. Automatic 'updated_at' Trigger Function
CREATE OR REPLACE FUNCTION update_timestamp_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_patients_updated_at ON patients;
CREATE TRIGGER trigger_patients_updated_at
BEFORE UPDATE ON patients
FOR EACH ROW
EXECUTE FUNCTION update_timestamp_column();

-- ============================================================================
-- 5. Bonus Table: Call Transcripts & Logs (Linked to Patient Record)
-- ============================================================================
CREATE TABLE IF NOT EXISTS call_logs (
    call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id UUID REFERENCES patients(patient_id) ON DELETE SET NULL,
    vapi_call_id VARCHAR(100),
    caller_phone VARCHAR(20) NOT NULL,
    call_status VARCHAR(50) DEFAULT 'completed',
    call_duration_seconds INTEGER,
    transcript TEXT,
    recording_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_call_logs_patient_id ON call_logs(patient_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_caller_phone ON call_logs(caller_phone);

-- ============================================================================
-- 6. Seed Data (Demonstration Records as requested by CareCloud)
-- ============================================================================
INSERT INTO patients (
    first_name,
    last_name,
    date_of_birth,
    sex,
    phone_number,
    email,
    address_line_1,
    address_line_2,
    city,
    state,
    zip_code,
    insurance_provider,
    insurance_member_id,
    preferred_language,
    emergency_contact_name,
    emergency_contact_phone
) VALUES 
(
    'Jane',
    'Doe',
    '1992-06-15',
    'Female',
    '3055550199',
    'jane.doe@example.com',
    '701 Brickell Ave',
    'Suite 1500',
    'Miami',
    'FL',
    '33131',
    'Blue Cross Blue Shield',
    'BCBS-987654321',
    'English',
    'John Doe',
    '3055550198'
),
(
    'Carlos',
    'Hernandez',
    '1985-11-20',
    'Male',
    '2125550144',
    'carlos.h@example.com',
    '350 5th Ave',
    'Apt 12B',
    'New York',
    'NY',
    '10118',
    'Aetna',
    'AET-445566778',
    'Spanish',
    'Maria Hernandez',
    '2125550145'
)
ON CONFLICT DO NOTHING;
