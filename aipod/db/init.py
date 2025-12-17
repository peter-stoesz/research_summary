"""Database initialization and schema management."""

from typing import Any, Dict

from psycopg.errors import DatabaseError

from .connection import get_connection


SCHEMA_SQL = """
-- Sources table
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0 AND weight <= 1),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Runs table
CREATE TABLE IF NOT EXISTS runs (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failed')),
    stats_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Articles table
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL REFERENCES sources(id),
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMP,
    outlet TEXT,
    content_hash TEXT NOT NULL,
    extracted_path TEXT NOT NULL,
    first_seen_at TIMESTAMP NOT NULL,
    last_seen_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(canonical_url)
);

-- Run articles link table
CREATE TABLE IF NOT EXISTS run_articles (
    run_id INTEGER NOT NULL REFERENCES runs(id),
    article_id INTEGER NOT NULL REFERENCES articles(id),
    included_in_rank BOOLEAN NOT NULL DEFAULT FALSE,
    score_json JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, article_id)
);

-- Clusters table (optional, for future clustering feature)
CREATE TABLE IF NOT EXISTS clusters (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES runs(id),
    representative_article_id INTEGER NOT NULL REFERENCES articles(id),
    title TEXT,
    cluster_metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Cluster members table
CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id INTEGER NOT NULL REFERENCES clusters(id),
    article_id INTEGER NOT NULL REFERENCES articles(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (cluster_id, article_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_content_hash ON articles(content_hash);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_run_articles_run_id ON run_articles(run_id);
CREATE INDEX IF NOT EXISTS idx_run_articles_article_id ON run_articles(article_id);
CREATE INDEX IF NOT EXISTS idx_clusters_run_id ON clusters(run_id);
CREATE INDEX IF NOT EXISTS idx_runs_run_date ON runs(run_date);

-- Update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create update triggers
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_runs_updated_at BEFORE UPDATE ON runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_articles_updated_at BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_run_articles_updated_at BEFORE UPDATE ON run_articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clusters_updated_at BEFORE UPDATE ON clusters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_cluster_members_updated_at BEFORE UPDATE ON cluster_members
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
"""


def validate_connection(config: Dict[str, Any]) -> bool:
    """Validate database connection."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                result = cur.fetchone()
                return result is not None and result["?column?"] == 1
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False


def init_database(config: Dict[str, Any]) -> None:
    """Initialize database schema."""
    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                # Execute schema SQL
                cur.execute(SCHEMA_SQL)
                conn.commit()
                print("Database schema initialized successfully")
    except DatabaseError as e:
        print(f"Failed to initialize database schema: {e}")
        raise