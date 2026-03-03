-- Generated: 2025-10-02 21:30:00 KST
-- OCR_MODEL_VERSIONS Table Creation
-- This table tracks trained OCR model versions and their performance metrics

CREATE TABLE OCR_MODEL_VERSIONS (
    model_id NUMBER(19) PRIMARY KEY,
    model_name VARCHAR2(200) NOT NULL,
    model_type VARCHAR2(50) NOT NULL,  -- 'detection', 'recognition', 'combined'
    version VARCHAR2(50) NOT NULL,
    model_path VARCHAR2(500),
    training_dataset_size NUMBER(10),
    training_start_date TIMESTAMP(6),
    training_end_date TIMESTAMP(6),
    precision NUMBER(5,4),  -- 0.0000 ~ 1.0000
    recall NUMBER(5,4),
    hmean NUMBER(5,4),
    fps NUMBER(8,2),
    is_active NUMBER(1) DEFAULT 1,  -- 1: active, 0: inactive
    notes VARCHAR2(2000),
    created_at TIMESTAMP(6) DEFAULT SYSTIMESTAMP,
    updated_at TIMESTAMP(6) DEFAULT SYSTIMESTAMP,
    CONSTRAINT uk_model_name_version UNIQUE (model_name, version),
    CONSTRAINT chk_model_type CHECK (model_type IN ('detection', 'recognition', 'combined')),
    CONSTRAINT chk_is_active CHECK (is_active IN (0, 1)),
    CONSTRAINT chk_precision_range CHECK (precision >= 0.0 AND precision <= 1.0),
    CONSTRAINT chk_recall_range CHECK (recall >= 0.0 AND recall <= 1.0),
    CONSTRAINT chk_hmean_range CHECK (hmean >= 0.0 AND hmean <= 1.0)
);

-- Sequence for model_id
CREATE SEQUENCE seq_ocr_model_versions
    START WITH 1
    INCREMENT BY 1
    NOCACHE
    NOCYCLE;

-- Index for performance queries
CREATE INDEX idx_model_versions_active ON OCR_MODEL_VERSIONS(is_active, model_type);
CREATE INDEX idx_model_versions_perf ON OCR_MODEL_VERSIONS(hmean, precision, recall);

-- Comments
COMMENT ON TABLE OCR_MODEL_VERSIONS IS 'OCR model version tracking and performance metrics';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.model_id IS 'Unique model ID (auto-increment)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.model_name IS 'Model name (e.g., PP-OCRv3_det)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.model_type IS 'Model type: detection, recognition, or combined';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.version IS 'Model version (e.g., v1.0.0, 2024-10-02)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.precision IS 'Model precision (0.0-1.0)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.recall IS 'Model recall (0.0-1.0)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.hmean IS 'Harmonic mean of precision and recall (F1 score)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.fps IS 'Inference speed (frames per second)';
COMMENT ON COLUMN OCR_MODEL_VERSIONS.is_active IS 'Active status: 1=active, 0=inactive';
