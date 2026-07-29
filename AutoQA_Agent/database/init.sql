CREATE TABLE IF NOT EXISTS analysis_reports (
    id VARCHAR(64) PRIMARY KEY,
    repository_name VARCHAR(255) NOT NULL,
    repository_url TEXT NOT NULL,
    report_json JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_reports_repository_name
ON analysis_reports(repository_name);
