"""Article storage and management."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from psycopg import Connection

from ..ingestion.models import ArticleContent, FeedItem
from ..models import Article, RunArticle


class ArticleStorage:
    """Handle article storage and deduplication."""

    def __init__(self, workspace_root: Path) -> None:
        """Initialize article storage."""
        self.workspace_root = workspace_root

    def _get_article_path(self, run_date: str, article_id: int) -> Path:
        """Get path for storing article text."""
        return (
            self.workspace_root
            / "runs"
            / run_date
            / "extracted"
            / f"article_{article_id}.txt"
        )

    def _save_article_text(self, path: Path, text: str) -> None:
        """Save article text to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def upsert_article(
        self,
        conn: Connection,
        article: ArticleContent,
        source_id: int,
        run_date: str,
    ) -> Tuple[int, bool]:
        """
        Upsert article to database.
        
        Returns:
            Tuple of (article_id, is_new)
        """
        with conn.cursor() as cur:
            # First, check if article already exists by canonical URL or content hash
            cur.execute(
                """
                SELECT id, content_hash, extracted_path
                FROM articles
                WHERE canonical_url = %s OR content_hash = %s
                LIMIT 1
                """,
                (article.canonical_url, article.content_hash),
            )
            
            existing = cur.fetchone()
            
            if existing:
                # Update last_seen_at
                cur.execute(
                    """
                    UPDATE articles
                    SET last_seen_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (existing["id"],),
                )
                return existing["id"], False
            
            # Insert new article
            cur.execute(
                """
                INSERT INTO articles (
                    source_id, canonical_url, title, published_at,
                    outlet, content_hash, extracted_path,
                    first_seen_at, last_seen_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                RETURNING id
                """,
                (
                    source_id,
                    article.canonical_url,
                    article.title,
                    article.published_at,
                    article.outlet,
                    article.content_hash,
                    "",  # Will update after saving file
                ),
            )
            
            article_id = cur.fetchone()["id"]
            
            # Save article text to file
            article_path = self._get_article_path(run_date, article_id)
            self._save_article_text(article_path, article.text)
            
            # Update extracted_path
            cur.execute(
                """
                UPDATE articles
                SET extracted_path = %s
                WHERE id = %s
                """,
                (str(article_path), article_id),
            )
            
            return article_id, True

    def link_article_to_run(
        self,
        conn: Connection,
        run_id: int,
        article_id: int,
    ) -> None:
        """Link article to run."""
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO run_articles (run_id, article_id, included_in_rank)
                VALUES (%s, %s, %s)
                ON CONFLICT (run_id, article_id) DO NOTHING
                """,
                (run_id, article_id, True),
            )

    def process_articles(
        self,
        conn: Connection,
        articles: List[ArticleContent],
        source_map: Dict[str, int],
        run_id: int,
        run_date: str,
    ) -> Dict[str, int]:
        """
        Process and store articles with deduplication.
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total": len(articles),
            "new": 0,
            "duplicates": 0,
            "failed": 0,
            "stored": 0,
        }
        
        for article in articles:
            if not article.fetch_success:
                stats["failed"] += 1
                continue
            
            # Get source ID using source name from RSS feed
            source_id = source_map.get(article.source_name)
            if not source_id:
                # Fallback: try to match by outlet domain (less reliable)
                for source_name, sid in source_map.items():
                    if article.outlet and article.outlet.lower() in source_name.lower():
                        source_id = sid
                        break
            
            if not source_id:
                continue
            
            # Upsert article
            article_id, is_new = self.upsert_article(
                conn, article, source_id, run_date
            )
            
            if is_new:
                stats["new"] += 1
            else:
                stats["duplicates"] += 1
            
            stats["stored"] += 1
            
            # Link to run
            self.link_article_to_run(conn, run_id, article_id)
        
        conn.commit()
        return stats

    def get_recent_articles(
        self,
        conn: Connection,
        limit: int = 100,
        days: int = 7,
    ) -> List[Dict]:
        """Get recent articles for novelty checking."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 
                    a.id,
                    a.canonical_url,
                    a.content_hash,
                    a.title,
                    a.published_at
                FROM articles a
                WHERE a.first_seen_at >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY a.first_seen_at DESC
                LIMIT %s
                """,
                (days, limit),
            )
            return cur.fetchall()

    def get_run_articles(
        self,
        conn: Connection,
        run_id: int,
        only_ranked: bool = False,
    ) -> List[Dict]:
        """Get articles for a specific run."""
        with conn.cursor() as cur:
            query = """
                SELECT 
                    a.*,
                    s.name as source_name,
                    s.weight as source_weight,
                    ra.included_in_rank,
                    ra.score_json
                FROM articles a
                JOIN run_articles ra ON a.id = ra.article_id
                JOIN sources s ON a.source_id = s.id
                WHERE ra.run_id = %s
            """
            
            if only_ranked:
                query += " AND ra.included_in_rank = TRUE"
            
            query += " ORDER BY a.published_at DESC"
            
            cur.execute(query, (run_id,))
            return cur.fetchall()