"""Source management in database."""

from typing import Dict, List

from psycopg import Connection

from ..config import SourceConfig


class SourceManager:
    """Manage sources in database."""

    def sync_sources(
        self,
        conn: Connection,
        sources: List[SourceConfig],
    ) -> Dict[str, int]:
        """
        Sync sources from config to database.
        
        Returns:
            Mapping of source name to database ID
        """
        source_map = {}
        
        with conn.cursor() as cur:
            for source in sources:
                # Upsert source
                cur.execute(
                    """
                    INSERT INTO sources (name, url, category, weight, enabled)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name) DO UPDATE SET
                        url = EXCLUDED.url,
                        category = EXCLUDED.category,
                        weight = EXCLUDED.weight,
                        enabled = EXCLUDED.enabled,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                    """,
                    (
                        source.name,
                        source.url,
                        source.category,
                        source.weight,
                        source.enabled,
                    ),
                )
                
                source_id = cur.fetchone()["id"]
                source_map[source.name] = source_id
        
        conn.commit()
        return source_map

    def get_sources(self, conn: Connection) -> List[Dict]:
        """Get all sources from database."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM sources
                ORDER BY name
                """
            )
            return cur.fetchall()

    def update_source_stats(
        self,
        conn: Connection,
        run_id: int,
    ) -> None:
        """Update source statistics after a run."""
        with conn.cursor() as cur:
            # This could be extended to track success rates, average article counts, etc.
            cur.execute(
                """
                UPDATE runs
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (run_id,),
            )
        conn.commit()