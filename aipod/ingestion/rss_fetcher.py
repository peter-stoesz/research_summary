"""RSS feed fetcher with concurrent processing."""

import asyncio
from datetime import datetime
from typing import List, Optional

import feedparser
import httpx
import pendulum
from rich.console import Console

from ..config import SourceConfig
from .models import FeedItem, FeedResult

console = Console()


class RSSFetcher:
    """Fetch and parse RSS feeds."""

    def __init__(self, timeout: float = 30.0, max_concurrent: int = 5) -> None:
        """Initialize RSS fetcher."""
        self.timeout = timeout
        self.max_concurrent = max_concurrent

    async def fetch_feed(self, source: SourceConfig) -> FeedResult:
        """Fetch and parse a single RSS feed."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(source.url)
                response.raise_for_status()
                
                # Parse RSS feed
                feed = feedparser.parse(response.text)
                
                if feed.bozo:
                    return FeedResult(
                        source_name=source.name,
                        source_url=source.url,
                        success=False,
                        error=f"Invalid RSS feed: {feed.bozo_exception}",
                    )
                
                # Extract feed items
                items = []
                for entry in feed.entries:
                    # Parse publication date
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            # Use feedparser's parsed time tuple
                            import time
                            published = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        except:
                            pass
                    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        try:
                            import time
                            published = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                        except:
                            pass
                    
                    # Get description
                    description = None
                    if hasattr(entry, "summary"):
                        description = entry.summary
                    elif hasattr(entry, "description"):
                        description = entry.description
                    
                    item = FeedItem(
                        title=entry.title,
                        link=entry.link,
                        published=published,
                        description=description,
                        source_name=source.name,
                    )
                    items.append(item)
                
                return FeedResult(
                    source_name=source.name,
                    source_url=source.url,
                    success=True,
                    items=items,
                    item_count=len(items),
                )
                
        except httpx.HTTPError as e:
            return FeedResult(
                source_name=source.name,
                source_url=source.url,
                success=False,
                error=f"HTTP error: {e}",
            )
        except Exception as e:
            return FeedResult(
                source_name=source.name,
                source_url=source.url,
                success=False,
                error=f"Unexpected error: {e}",
            )

    async def fetch_all_feeds(self, sources: List[SourceConfig]) -> List[FeedResult]:
        """Fetch all RSS feeds concurrently."""
        # Filter enabled sources
        enabled_sources = [s for s in sources if s.enabled]
        
        if not enabled_sources:
            return []
        
        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def fetch_with_semaphore(source: SourceConfig) -> FeedResult:
            async with semaphore:
                return await self.fetch_feed(source)
        
        # Fetch all feeds concurrently
        tasks = [fetch_with_semaphore(source) for source in enabled_sources]
        results = await asyncio.gather(*tasks)
        
        return results

    def fetch_feeds_sync(self, sources: List[SourceConfig]) -> List[FeedResult]:
        """Synchronous wrapper for fetch_all_feeds."""
        return asyncio.run(self.fetch_all_feeds(sources))


def print_feed_summary(results: List[FeedResult]) -> None:
    """Print summary of feed fetch results."""
    total_items = sum(r.item_count for r in results)
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    
    console.print(f"\n[bold]RSS Feed Summary:[/bold]")
    console.print(f"  Sources fetched: {len(results)}")
    console.print(f"  Successful: [green]{successful}[/green]")
    console.print(f"  Failed: [red]{failed}[/red]")
    console.print(f"  Total items: {total_items}")
    
    if failed > 0:
        console.print(f"\n[bold red]Failed feeds:[/bold red]")
        for result in results:
            if not result.success:
                console.print(f"  - {result.source_name}: {result.error}")