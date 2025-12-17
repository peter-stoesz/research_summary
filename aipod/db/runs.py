"""Run management in database."""

import json
from datetime import datetime
from typing import Dict, Optional

from psycopg import Connection

from ..models import Run


class RunManager:
    """Manage pipeline runs in database."""

    def create_run(
        self,
        conn: Connection,
        run_date: str,
        started_at: Optional[datetime] = None,
    ) -> int:
        """
        Create a new run record.
        
        Returns:
            Run ID
        """
        if started_at is None:
            started_at = datetime.now()
        
        with conn.cursor() as cur:
            # Check if run for this date already exists
            cur.execute(
                "SELECT id FROM runs WHERE run_date = %s ORDER BY started_at DESC LIMIT 1",
                (run_date,)
            )
            existing = cur.fetchone()
            
            if existing:
                # Update existing run
                cur.execute(
                    """
                    UPDATE runs 
                    SET 
                        started_at = %s,
                        finished_at = NULL,
                        status = 'running',
                        stats_json = NULL
                    WHERE id = %s
                    RETURNING id
                    """,
                    (started_at, existing["id"])
                )
                run_id = cur.fetchone()["id"]
            else:
                # Create new run
                cur.execute(
                    """
                    INSERT INTO runs (run_date, started_at, status)
                    VALUES (%s, %s, 'running')
                    RETURNING id
                    """,
                    (run_date, started_at)
                )
                run_id = cur.fetchone()["id"]
        
        conn.commit()
        return run_id

    def update_run_status(
        self,
        conn: Connection,
        run_id: int,
        status: str,
        stats_json: Optional[Dict] = None,
        finished_at: Optional[datetime] = None,
    ) -> None:
        """Update run status and statistics."""
        if finished_at is None and status in ["success", "failed"]:
            finished_at = datetime.now()
        
        with conn.cursor() as cur:
            # Convert dict to JSON string if provided
            stats_json_str = json.dumps(stats_json) if stats_json else None
            
            cur.execute(
                """
                UPDATE runs
                SET 
                    status = %s,
                    finished_at = %s,
                    stats_json = %s
                WHERE id = %s
                """,
                (status, finished_at, stats_json_str, run_id)
            )
        
        conn.commit()

    def get_run(self, conn: Connection, run_id: int) -> Optional[Dict]:
        """Get run by ID."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM runs WHERE id = %s",
                (run_id,)
            )
            return cur.fetchone()

    def get_recent_runs(
        self,
        conn: Connection,
        limit: int = 10,
    ) -> list[Dict]:
        """Get recent runs."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM runs 
                ORDER BY started_at DESC 
                LIMIT %s
                """,
                (limit,)
            )
            return cur.fetchall()

    def get_run_by_date(
        self,
        conn: Connection,
        run_date: str,
    ) -> Optional[Dict]:
        """Get most recent run for a specific date."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM runs 
                WHERE run_date = %s 
                ORDER BY started_at DESC 
                LIMIT 1
                """,
                (run_date,)
            )
            return cur.fetchone()