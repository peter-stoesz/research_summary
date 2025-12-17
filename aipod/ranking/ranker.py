"""Article ranker that combines multiple scoring components."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pendulum
from psycopg import Connection
from rich.console import Console

from ..config import RankingConfig
from ..db.articles import ArticleStorage
from .models import ArticleScore, RankingResult
from .scorers import (
    NoveltyScorer,
    PreferenceScorer,
    RecencyScorer,
    SourceScorer,
    TopicScorer,
)

console = Console()


class ArticleRanker:
    """Rank articles using multiple scoring components."""

    def __init__(
        self,
        config: RankingConfig,
        workspace_root: Path,
        preferences: Optional[Dict] = None,
    ) -> None:
        """
        Initialize article ranker.
        
        Args:
            config: Ranking configuration
            workspace_root: Workspace root for reading article content
            preferences: User preferences for scoring
        """
        self.config = config
        self.workspace_root = workspace_root
        self.preferences = preferences or {}
        
        # Initialize scorers
        self.recency_scorer = RecencyScorer(half_life_hours=48.0)
        self.source_scorer = SourceScorer()
        self.topic_scorer = TopicScorer(
            boost_keywords=self.preferences.get("boost_keywords", []),
            suppress_keywords=self.preferences.get("suppress_keywords", []),
        )
        self.novelty_scorer = NoveltyScorer()
        self.preference_scorer = PreferenceScorer(
            preferred_outlets=self.preferences.get("preferred_outlets", []),
            preferred_categories=self.preferences.get("preferred_categories", []),
        )

    def _load_article_content(self, article_path: str) -> Optional[str]:
        """Load article content from file."""
        try:
            path = Path(article_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            pass
        return None

    def _generate_reason(self, scores: Dict[str, float], article: Dict) -> str:
        """Generate human-readable reason for score."""
        reasons = []
        
        # Find dominant factors
        if scores["recency"] >= 0.8:
            reasons.append("Very recent article")
        elif scores["recency"] <= 0.3:
            reasons.append("Older article")
        
        if scores["source"] >= 0.9:
            reasons.append("from high-quality source")
        
        if scores["topic"] >= 0.8:
            reasons.append("highly relevant to interests")
        elif scores["topic"] <= 0.2:
            reasons.append("low topic relevance")
        
        if scores["novelty"] <= 0.3:
            reasons.append("similar to recent coverage")
        
        if not reasons:
            reasons.append("Balanced scoring across factors")
        
        return "; ".join(reasons) + f" ({article.get('outlet', 'unknown source')})"

    def score_article(
        self,
        article: Dict,
        recent_articles: List[Dict],
        source_category: Optional[str] = None,
    ) -> ArticleScore:
        """Score a single article."""
        # Load article content if available
        content = ""
        if article.get("extracted_path"):
            content = self._load_article_content(article["extracted_path"]) or ""
        
        # Prepare context
        context = {
            "recent_articles": recent_articles,
            "content": content,
            "source_category": source_category or "",
        }
        
        # Calculate individual scores
        scores = {
            "recency": self.recency_scorer.score(article, context),
            "source": self.source_scorer.score(article, context),
            "topic": self.topic_scorer.score(article, context),
            "novelty": self.novelty_scorer.score(article, context),
            "preference": self.preference_scorer.score(article, context),
        }
        
        # Calculate weighted total
        total = (
            scores["recency"] * self.config.recency_weight +
            scores["source"] * self.config.source_weight +
            scores["topic"] * self.config.topic_weight +
            scores["novelty"] * self.config.novelty_weight +
            scores["preference"] * (1 - self.config.recency_weight - 
                                   self.config.source_weight - 
                                   self.config.topic_weight - 
                                   self.config.novelty_weight)
        )
        
        # Generate reason
        reason = self._generate_reason(scores, article)
        
        return ArticleScore(
            article_id=article["id"],
            total_score=total,
            recency_score=scores["recency"],
            source_score=scores["source"],
            topic_score=scores["topic"],
            novelty_score=scores["novelty"],
            preference_score=scores["preference"],
            reason=reason,
            debug_info={
                "title": article.get("title", ""),
                "published": str(article.get("published_at", "")),
                "outlet": article.get("outlet", ""),
            },
        )

    def rank_articles(
        self,
        conn: Connection,
        run_id: int,
        max_stories: int = 20,
        min_score: float = 0.1,
    ) -> RankingResult:
        """
        Rank articles for a run.
        
        Args:
            conn: Database connection
            run_id: Run ID
            max_stories: Maximum number of stories to select
            min_score: Minimum score threshold
            
        Returns:
            Ranking result with scored articles
        """
        storage = ArticleStorage(self.workspace_root)
        
        # Get articles for this run
        articles = storage.get_run_articles(conn, run_id)
        
        if not articles:
            return RankingResult(
                run_id=run_id,
                total_articles=0,
                ranked_articles=[],
                ranking_timestamp=pendulum.now(),
                config_used=self.config.model_dump(),
            )
        
        # Get recent articles for novelty scoring
        recent_articles = storage.get_recent_articles(
            conn, 
            limit=200,
            days=self.config.novelty_window_runs * 7,  # Approximate days
        )
        
        # Create source category map
        source_categories = {
            article["source_name"]: article.get("category", "")
            for article in articles
        }
        
        # Score all articles
        scored_articles = []
        for article in articles:
            source_category = source_categories.get(article["source_name"])
            score = self.score_article(article, recent_articles, source_category)
            
            if score.total_score >= min_score:
                scored_articles.append(score)
        
        # Sort by total score descending
        scored_articles.sort(key=lambda x: x.total_score, reverse=True)
        
        # Select top stories
        selected = scored_articles[:max_stories]
        
        # Update database with scores
        with conn.cursor() as cur:
            for score in selected:
                score_json = {
                    "total": score.total_score,
                    "recency": score.recency_score,
                    "source": score.source_score,
                    "topic": score.topic_score,
                    "novelty": score.novelty_score,
                    "preference": score.preference_score,
                    "reason": score.reason,
                }
                
                cur.execute(
                    """
                    UPDATE run_articles
                    SET 
                        included_in_rank = TRUE,
                        score_json = %s
                    WHERE run_id = %s AND article_id = %s
                    """,
                    (json.dumps(score_json), run_id, score.article_id),
                )
        
        conn.commit()
        
        return RankingResult(
            run_id=run_id,
            total_articles=len(articles),
            ranked_articles=selected,
            ranking_timestamp=pendulum.now(),
            config_used=self.config.model_dump(),
        )


def print_ranking_summary(result: RankingResult) -> None:
    """Print ranking summary."""
    console.print(f"\n[bold]Ranking Summary:[/bold]")
    console.print(f"  Total articles: {result.total_articles}")
    console.print(f"  Selected stories: {len(result.ranked_articles)}")
    
    if result.ranked_articles:
        console.print(f"\n[bold]Top Stories:[/bold]")
        for i, score in enumerate(result.ranked_articles[:10], 1):
            console.print(
                f"{i}. [yellow]{score.debug_info.get('title', 'Unknown')}[/yellow]"
            )
            console.print(f"   Score: {score.total_score:.3f} - {score.reason}")
            console.print(
                f"   Breakdown: R:{score.recency_score:.2f} "
                f"S:{score.source_score:.2f} T:{score.topic_score:.2f} "
                f"N:{score.novelty_score:.2f} P:{score.preference_score:.2f}"
            )