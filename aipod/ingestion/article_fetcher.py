"""Article fetcher and text extractor."""

import asyncio
import hashlib
from typing import List, Optional
from urllib.parse import urlparse

import httpx
import trafilatura
from rich.console import Console

from .models import ArticleContent, FeedItem

console = Console()


class ArticleFetcher:
    """Fetch HTML and extract article text."""

    def __init__(
        self,
        timeout: float = 30.0,
        max_concurrent: int = 3,
        user_agent: str = "AIpod/1.0 (AI Podcast Agent)",
    ) -> None:
        """Initialize article fetcher."""
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.user_agent = user_agent

    def _normalize_text(self, text: str) -> str:
        """Normalize text for hashing."""
        # Remove extra whitespace and normalize line endings
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines).lower()

    def _compute_content_hash(self, text: str) -> str:
        """Compute hash of normalized text."""
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()

    def _extract_outlet(self, url: str) -> str:
        """Extract outlet/domain from URL."""
        parsed = urlparse(url)
        domain = parsed.hostname or "unknown"
        # Remove common prefixes
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    async def fetch_article(self, item: FeedItem) -> ArticleContent:
        """Fetch and extract a single article."""
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml",
            }
            
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:
                response = await client.get(item.link)
                response.raise_for_status()
                
                # Check for paywall indicators
                if any(
                    indicator in response.text.lower()
                    for indicator in ["paywall", "subscribe to read", "members only"]
                ):
                    return ArticleContent(
                        url=item.link,
                        canonical_url=str(response.url),
                        title=item.title,
                        text="",
                        outlet=self._extract_outlet(str(response.url)),
                        published_at=item.published,
                        content_hash="",
                        fetch_success=False,
                        error="Paywall detected",
                        source_name=item.source_name,
                    )
                
                # Extract main content using trafilatura
                extracted = trafilatura.extract(
                    response.text,
                    include_comments=False,
                    include_tables=False,
                    deduplicate=True,
                    favor_precision=True,
                    url=str(response.url),
                )
                
                if not extracted:
                    return ArticleContent(
                        url=item.link,
                        canonical_url=str(response.url),
                        title=item.title,
                        text="",
                        outlet=self._extract_outlet(str(response.url)),
                        published_at=item.published,
                        content_hash="",
                        fetch_success=False,
                        error="Failed to extract article content",
                        source_name=item.source_name,
                    )
                
                # Compute content hash
                content_hash = self._compute_content_hash(extracted)
                
                # Extract metadata if available
                metadata = trafilatura.metadata.extract_metadata(response.text)
                
                # Use metadata date if feed date is missing
                published_at = item.published
                if not published_at and metadata and metadata.date:
                    try:
                        published_at = metadata.date
                    except:
                        pass
                
                return ArticleContent(
                    url=item.link,
                    canonical_url=str(response.url),
                    title=metadata.title or item.title if metadata else item.title,
                    text=extracted,
                    outlet=self._extract_outlet(str(response.url)),
                    published_at=published_at,
                    content_hash=content_hash,
                    fetch_success=True,
                    source_name=item.source_name,
                )
                
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}"
            if e.response.status_code == 404:
                error_msg = "Article not found (404)"
            elif e.response.status_code == 403:
                error_msg = "Access forbidden (403)"
            elif e.response.status_code >= 500:
                error_msg = f"Server error ({e.response.status_code})"
                
            return ArticleContent(
                url=item.link,
                canonical_url=item.link,
                title=item.title,
                text="",
                outlet=self._extract_outlet(item.link),
                published_at=item.published,
                content_hash="",
                fetch_success=False,
                error=error_msg,
                source_name=item.source_name,
            )
        except httpx.TimeoutException:
            return ArticleContent(
                url=item.link,
                canonical_url=item.link,
                title=item.title,
                text="",
                outlet=self._extract_outlet(item.link),
                published_at=item.published,
                content_hash="",
                fetch_success=False,
                error="Request timed out",
                source_name=item.source_name,
            )
        except Exception as e:
            return ArticleContent(
                url=item.link,
                canonical_url=item.link,
                title=item.title,
                text="",
                outlet=self._extract_outlet(item.link),
                published_at=item.published,
                content_hash="",
                fetch_success=False,
                error=f"Unexpected error: {str(e)}",
                source_name=item.source_name,
            )

    async def fetch_all_articles(self, items: List[FeedItem]) -> List[ArticleContent]:
        """Fetch all articles concurrently."""
        if not items:
            return []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_semaphore(item: FeedItem) -> ArticleContent:
            async with semaphore:
                return await self.fetch_article(item)
        
        # Fetch all articles concurrently
        tasks = [fetch_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks)
        
        return results

    def fetch_articles_sync(self, items: List[FeedItem]) -> List[ArticleContent]:
        """Synchronous wrapper for fetch_all_articles."""
        return asyncio.run(self.fetch_all_articles(items))


def print_fetch_summary(articles: List[ArticleContent]) -> None:
    """Print summary of article fetch results."""
    successful = sum(1 for a in articles if a.fetch_success)
    failed = len(articles) - successful
    
    console.print(f"\n[bold]Article Fetch Summary:[/bold]")
    console.print(f"  Total articles: {len(articles)}")
    console.print(f"  Successful: [green]{successful}[/green]")
    console.print(f"  Failed: [red]{failed}[/red]")
    
    if failed > 0:
        console.print(f"\n[bold red]Failed articles:[/bold red]")
        error_counts = {}
        for article in articles:
            if not article.fetch_success:
                error = article.error or "Unknown error"
                error_counts[error] = error_counts.get(error, 0) + 1
        
        for error, count in sorted(error_counts.items()):
            console.print(f"  - {error}: {count}")