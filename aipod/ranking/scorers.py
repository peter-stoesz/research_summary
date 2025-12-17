"""Individual scoring components for article ranking."""

import math
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

import pendulum


class BaseScorer(ABC):
    """Base class for scoring components."""

    @abstractmethod
    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """
        Score an article from 0.0 to 1.0.
        
        Args:
            article: Article data from database
            context: Additional context (e.g., recent articles, config)
            
        Returns:
            Score between 0.0 and 1.0
        """
        pass


class RecencyScorer(BaseScorer):
    """Score based on article recency with exponential decay."""

    def __init__(self, half_life_hours: float = 48.0) -> None:
        """
        Initialize recency scorer.
        
        Args:
            half_life_hours: Hours for score to decay by 50%
        """
        self.half_life_hours = half_life_hours

    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """Score based on publication date recency."""
        if not article.get("published_at"):
            return 0.5  # Neutral score for missing date
        
        published = article["published_at"]
        if isinstance(published, str):
            published = pendulum.parse(published)
        elif hasattr(published, 'replace') and published.tzinfo is None:
            # Convert naive datetime to UTC timezone-aware
            published = pendulum.instance(published, tz='UTC')
        
        now = pendulum.now('UTC')
        age_hours = (now - published).total_seconds() / 3600
        
        # Exponential decay formula
        decay_rate = math.log(2) / self.half_life_hours
        score = math.exp(-decay_rate * age_hours)
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, score))


class SourceScorer(BaseScorer):
    """Score based on source weight."""

    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """Score based on source weight."""
        weight = article.get("source_weight", 1.0)
        return max(0.0, min(1.0, float(weight)))


class TopicScorer(BaseScorer):
    """Score based on topic relevance using keywords."""

    def __init__(
        self,
        boost_keywords: List[str] = None,
        suppress_keywords: List[str] = None,
        title_weight: float = 2.0,
    ) -> None:
        """
        Initialize topic scorer.
        
        Args:
            boost_keywords: Keywords to boost score
            suppress_keywords: Keywords to suppress score
            title_weight: How much more to weight title matches
        """
        self.boost_keywords = [k.lower() for k in (boost_keywords or [])]
        self.suppress_keywords = [k.lower() for k in (suppress_keywords or [])]
        self.title_weight = title_weight

    def _count_matches(self, text: str, keywords: List[str]) -> Dict[str, int]:
        """Count keyword matches in text."""
        text_lower = text.lower()
        matches = {}
        
        for keyword in keywords:
            # Use word boundaries for more accurate matching
            pattern = r'\b' + re.escape(keyword) + r'\b'
            count = len(re.findall(pattern, text_lower))
            if count > 0:
                matches[keyword] = count
        
        return matches

    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """Score based on keyword matches."""
        title = article.get("title", "")
        
        # Get content if available in context
        content = ""
        if context and "content" in context:
            content = context["content"]
        
        # Count matches
        title_boosts = self._count_matches(title, self.boost_keywords)
        content_boosts = self._count_matches(content, self.boost_keywords)
        title_suppressions = self._count_matches(title, self.suppress_keywords)
        content_suppressions = self._count_matches(content, self.suppress_keywords)
        
        # Calculate scores
        boost_score = 0.0
        for keyword, count in title_boosts.items():
            boost_score += count * self.title_weight
        for keyword, count in content_boosts.items():
            boost_score += count
        
        suppress_score = 0.0
        for keyword, count in title_suppressions.items():
            suppress_score += count * self.title_weight
        for keyword, count in content_suppressions.items():
            suppress_score += count
        
        # Normalize scores
        if boost_score > 0:
            boost_score = min(1.0, boost_score / 10.0)  # Cap at 10 matches
        if suppress_score > 0:
            suppress_score = min(1.0, suppress_score / 5.0)  # More aggressive suppression
        
        # Base score of 0.5, boosted or suppressed by keywords
        score = 0.5 + (boost_score * 0.5) - (suppress_score * 0.5)
        
        return max(0.0, min(1.0, score))


class NoveltyScorer(BaseScorer):
    """Score based on novelty compared to recent articles."""

    def __init__(self, similarity_threshold: float = 0.85) -> None:
        """
        Initialize novelty scorer.
        
        Args:
            similarity_threshold: Threshold for considering articles similar
        """
        self.similarity_threshold = similarity_threshold

    def _is_similar(self, article1: Dict, article2: Dict) -> bool:
        """Check if two articles are similar."""
        # Same canonical URL
        if article1.get("canonical_url") == article2.get("canonical_url"):
            return True
        
        # Same content hash
        if (article1.get("content_hash") and 
            article1["content_hash"] == article2.get("content_hash")):
            return True
        
        # Very similar titles (simple approach)
        title1 = article1.get("title", "").lower()
        title2 = article2.get("title", "").lower()
        
        if title1 and title2:
            # Check for significant overlap
            words1 = set(title1.split())
            words2 = set(title2.split())
            
            if len(words1) > 3 and len(words2) > 3:
                overlap = len(words1 & words2)
                similarity = overlap / min(len(words1), len(words2))
                if similarity >= self.similarity_threshold:
                    return True
        
        return False

    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """Score based on novelty compared to recent articles."""
        if not context or "recent_articles" not in context:
            return 1.0  # Assume novel if no context
        
        recent_articles = context["recent_articles"]
        
        # Check for similarity with recent articles
        for recent in recent_articles:
            if recent["id"] != article["id"] and self._is_similar(article, recent):
                # Penalize based on how recent the similar article is
                days_ago = 0
                if recent.get("first_seen_at"):
                    first_seen = recent["first_seen_at"]
                    if isinstance(first_seen, str):
                        first_seen = pendulum.parse(first_seen)
                    days_ago = (pendulum.now() - first_seen).days
                
                if days_ago <= 1:
                    return 0.1  # Very low score for very recent duplicates
                elif days_ago <= 3:
                    return 0.3  # Low score for recent duplicates
                else:
                    return 0.5  # Medium score for older duplicates
        
        return 1.0  # Full score for novel articles


class PreferenceScorer(BaseScorer):
    """Score based on user preferences beyond keywords."""

    def __init__(
        self,
        preferred_outlets: List[str] = None,
        preferred_categories: List[str] = None,
    ) -> None:
        """
        Initialize preference scorer.
        
        Args:
            preferred_outlets: List of preferred outlets/domains
            preferred_categories: List of preferred categories
        """
        self.preferred_outlets = [o.lower() for o in (preferred_outlets or [])]
        self.preferred_categories = [c.lower() for c in (preferred_categories or [])]

    def score(self, article: Dict, context: Optional[Dict] = None) -> float:
        """Score based on user preferences."""
        score = 0.5  # Base neutral score
        
        # Check outlet preference
        outlet = article.get("outlet", "").lower()
        if outlet and any(pref in outlet for pref in self.preferred_outlets):
            score += 0.25
        
        # Check category preference (from source)
        if context and "source_category" in context:
            category = context["source_category"].lower()
            if category in self.preferred_categories:
                score += 0.25
        
        return max(0.0, min(1.0, score))