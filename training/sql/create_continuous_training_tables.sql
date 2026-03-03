-- Generated: 2025-10-02 22:56:00 KST
-- Continuous Training System Database Tables

-- 1. 데이터 품질 메트릭 테이블
CREATE TABLE DATA_QUALITY_METRICS (
    metric_id NUMBER PRIMARY KEY,
    capture_id NUMBER NOT NULL,
    bbox_count NUMBER,
    avg_bbox_area NUMBER,
    bbox_density NUMBER,
    text_clarity_score NUMBER,
    image_quality_score NUMBER,
    quality_score NUMBER,
    is_valid CHAR(1) DEFAULT 'N',
    invalid_reason VARCHAR2(500),
    calculated_at TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT fk_dqm_capture FOREIGN KEY (capture_id)
        REFERENCES WEB_CAPTURE_DATA(capture_id),
    CONSTRAINT chk_dqm_valid CHECK (is_valid IN ('Y', 'N'))
);

CREATE SEQUENCE DATA_QUALITY_METRICS_SEQ START WITH 1 INCREMENT BY 1;

CREATE INDEX idx_dqm_capture_id ON DATA_QUALITY_METRICS(capture_id);
CREATE INDEX idx_dqm_quality_score ON DATA_QUALITY_METRICS(quality_score);
CREATE INDEX idx_dqm_is_valid ON DATA_QUALITY_METRICS(is_valid);

-- 2. 학습 이력 테이블 (중복 학습 방지)
CREATE TABLE TRAINING_HISTORY (
    training_id NUMBER PRIMARY KEY,
    capture_id NUMBER NOT NULL,
    training_batch_id VARCHAR2(100) NOT NULL,
    training_start_time TIMESTAMP,
    training_end_time TIMESTAMP,
    is_successful CHAR(1) DEFAULT 'P',
    loss_value NUMBER,
    epoch_trained NUMBER,
    CONSTRAINT fk_th_capture FOREIGN KEY (capture_id)
        REFERENCES WEB_CAPTURE_DATA(capture_id),
    CONSTRAINT chk_th_success CHECK (is_successful IN ('Y', 'N', 'P'))
);

CREATE SEQUENCE TRAINING_HISTORY_SEQ START WITH 1 INCREMENT BY 1;

CREATE INDEX idx_th_capture_id ON TRAINING_HISTORY(capture_id);
CREATE INDEX idx_th_batch_id ON TRAINING_HISTORY(training_batch_id);
CREATE INDEX idx_th_success ON TRAINING_HISTORY(is_successful);
CREATE INDEX idx_th_start_time ON TRAINING_HISTORY(training_start_time);

-- 3. 학습 반복 결과 테이블
CREATE TABLE TRAINING_ITERATION_RESULTS (
    iteration_id NUMBER PRIMARY KEY,
    iteration_num NUMBER NOT NULL,
    model_id NUMBER NOT NULL,
    precision_score NUMBER,
    recall_score NUMBER,
    hmean_score NUMBER,
    fps NUMBER,
    training_duration_hours NUMBER,
    goals_achieved CHAR(1) DEFAULT 'N',
    created_at TIMESTAMP DEFAULT SYSTIMESTAMP,
    CONSTRAINT fk_tir_model FOREIGN KEY (model_id)
        REFERENCES OCR_MODEL_VERSIONS(model_id),
    CONSTRAINT chk_tir_goals CHECK (goals_achieved IN ('Y', 'N'))
);

CREATE SEQUENCE TRAINING_ITERATION_SEQ START WITH 1 INCREMENT BY 1;

CREATE INDEX idx_tir_iteration_num ON TRAINING_ITERATION_RESULTS(iteration_num);
CREATE INDEX idx_tir_model_id ON TRAINING_ITERATION_RESULTS(model_id);
CREATE INDEX idx_tir_hmean ON TRAINING_ITERATION_RESULTS(hmean_score);
CREATE INDEX idx_tir_goals ON TRAINING_ITERATION_RESULTS(goals_achieved);

-- 4. WEB_CAPTURE_DATA 테이블에 삭제 정보 컬럼 추가 (이미 존재하면 skip)
BEGIN
    EXECUTE IMMEDIATE 'ALTER TABLE WEB_CAPTURE_DATA ADD (
        deleted_at TIMESTAMP,
        deletion_reason VARCHAR2(500)
    )';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLCODE = -1430 THEN  -- Column already exists
            NULL;
        ELSE
            RAISE;
        END IF;
END;
/

CREATE INDEX idx_wcd_deleted_at ON WEB_CAPTURE_DATA(deleted_at);

-- 5. 뷰: 학습 가능한 데이터 (품질 기준 통과 + 미학습)
CREATE OR REPLACE VIEW V_TRAINABLE_DATA AS
SELECT
    wcd.capture_id,
    wcd.URL as source_url,
    wcd.created_at,
    dqm.quality_score,
    dqm.bbox_count,
    dqm.text_clarity_score,
    dqm.image_quality_score
FROM WEB_CAPTURE_DATA wcd
INNER JOIN DATA_QUALITY_METRICS dqm ON wcd.capture_id = dqm.capture_id
LEFT JOIN TRAINING_HISTORY th ON wcd.capture_id = th.capture_id AND th.is_successful = 'Y'
WHERE wcd.deleted_at IS NULL
  AND dqm.is_valid = 'Y'
  AND th.training_id IS NULL
ORDER BY dqm.quality_score DESC, wcd.created_at DESC;

-- 6. 뷰: 학습 진행 현황
CREATE OR REPLACE VIEW V_TRAINING_PROGRESS AS
SELECT
    COUNT(DISTINCT capture_id) as total_samples,
    COUNT(DISTINCT CASE WHEN is_successful = 'Y' THEN capture_id END) as trained_samples,
    COUNT(DISTINCT CASE WHEN is_successful = 'N' THEN capture_id END) as failed_samples,
    COUNT(DISTINCT CASE WHEN is_successful = 'P' THEN capture_id END) as training_samples,
    ROUND(COUNT(DISTINCT CASE WHEN is_successful = 'Y' THEN capture_id END) * 100.0 /
          NULLIF(COUNT(DISTINCT capture_id), 0), 2) as success_rate
FROM TRAINING_HISTORY;

-- 7. 통계 정보 수집 (성능 최적화)
BEGIN
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'DATA_QUALITY_METRICS');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'TRAINING_HISTORY');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'TRAINING_ITERATION_RESULTS');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'WEB_CAPTURE_DATA');
END;
/

-- 8. 테이블 생성 확인
SELECT 'DATA_QUALITY_METRICS' as table_name, COUNT(*) as row_count FROM DATA_QUALITY_METRICS
UNION ALL
SELECT 'TRAINING_HISTORY', COUNT(*) FROM TRAINING_HISTORY
UNION ALL
SELECT 'TRAINING_ITERATION_RESULTS', COUNT(*) FROM TRAINING_ITERATION_RESULTS;

COMMIT;
