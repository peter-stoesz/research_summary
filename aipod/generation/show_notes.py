"""Show notes generator."""

import time
from pathlib import Path
from typing import Dict, List

import pendulum
from psycopg import Connection
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..db.articles import ArticleStorage
from .llm_provider import LLMProvider
from .models import ArticleSummary, GenerationStats, ShowNotes, ShowNotesSection

console = Console()


class ShowNotesGenerator:
    """Generate structured show notes from ranked articles."""

    def __init__(self, llm_provider: LLMProvider, workspace_root: Path) -> None:
        """
        Initialize show notes generator.
        
        Args:
            llm_provider: LLM provider for summarization
            workspace_root: Workspace root for reading article content
        """
        self.llm_provider = llm_provider
        self.workspace_root = workspace_root

    def _load_article_content(self, article_path: str) -> str:
        """Load article content from file."""
        try:
            path = Path(article_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
        except Exception:
            pass
        return ""

    def _format_date(self, date_obj) -> str:
        """Format date for display."""
        if not date_obj:
            return "Unknown date"
        
        if isinstance(date_obj, str):
            try:
                date_obj = pendulum.parse(date_obj)
            except:
                return "Unknown date"
        elif hasattr(date_obj, 'year') and not hasattr(date_obj, 'format'):
            # Convert Python datetime to Pendulum
            try:
                date_obj = pendulum.instance(date_obj)
            except:
                return "Unknown date"
        
        return date_obj.format("MMM DD, YYYY")

    def _categorize_articles(self, articles: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize articles into sections."""
        categories = {
            "Deployments & Implementations": [],
            "Product Launches & Updates": [],
            "Research & Breakthroughs": [],
            "Industry & Business": [],
            "Policy & Governance": [],
        }
        
        # Simple categorization based on keywords and source category
        for article in articles:
            title_lower = article.get("title", "").lower()
            content = self._load_article_content(article.get("extracted_path", ""))
            content_lower = content.lower()
            source_category = article.get("category", "").lower()
            
            # Keywords for categorization
            if any(word in title_lower or word in content_lower[:500] for word in [
                "deploy", "production", "enterprise", "implementation", "rollout", "launch"
            ]):
                categories["Deployments & Implementations"].append(article)
            elif any(word in title_lower for word in [
                "releases", "announces", "unveils", "launches", "introduces", "available"
            ]):
                categories["Product Launches & Updates"].append(article)
            elif any(word in title_lower or source_category for word in [
                "research", "study", "paper", "breakthrough", "discovery", "mit", "stanford"
            ]):
                categories["Research & Breakthroughs"].append(article)
            elif any(word in title_lower or word in content_lower[:500] for word in [
                "funding", "investment", "acquisition", "partnership", "revenue", "ipo"
            ]):
                categories["Industry & Business"].append(article)
            elif any(word in title_lower or word in content_lower[:500] for word in [
                "regulation", "policy", "law", "government", "congress", "senate"
            ]):
                categories["Policy & Governance"].append(article)
            else:
                # Default to implementations if no clear category
                categories["Deployments & Implementations"].append(article)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _summarize_article(self, article: Dict) -> ArticleSummary:
        """Summarize a single article."""
        title = article.get("title", "Unknown title")
        url = article.get("canonical_url", "")
        outlet = article.get("outlet", "Unknown source")
        published_date = self._format_date(article.get("published_at"))
        
        # Load article content
        content = self._load_article_content(article.get("extracted_path", ""))
        
        # Get summary from LLM
        bullet_points = self.llm_provider.summarize_article(
            title=title,
            content=content,
            url=url,
            outlet=outlet,
            max_bullets=4,
        )
        
        return ArticleSummary(
            article_id=article["id"],
            title=title,
            url=url,
            outlet=outlet,
            published_date=published_date,
            bullet_points=bullet_points,
            category=article.get("category", "unknown"),
        )

    def generate_show_notes(
        self,
        conn: Connection,
        run_id: int,
        run_date: str,
    ) -> tuple[ShowNotes, GenerationStats]:
        """
        Generate show notes for a run.
        
        Returns:
            Tuple of (show_notes, generation_stats)
        """
        start_time = time.time()
        
        # Get ranked articles for this run
        storage = ArticleStorage(self.workspace_root)
        articles = storage.get_run_articles(conn, run_id, only_ranked=True)
        
        if not articles:
            empty_notes = ShowNotes(
                run_date=run_date,
                sections=[],
                total_articles=0,
                generation_timestamp=pendulum.now().to_iso8601_string(),
            )
            empty_stats = GenerationStats(
                articles_processed=0,
                processing_time=time.time() - start_time,
            )
            return empty_notes, empty_stats
        
        # Categorize articles
        categorized = self._categorize_articles(articles)
        
        # Generate summaries with progress bar
        sections = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for category, category_articles in categorized.items():
                if not category_articles:
                    continue
                
                task = progress.add_task(
                    f"Summarizing {category} ({len(category_articles)} articles)...",
                    total=len(category_articles),
                )
                
                summaries = []
                for article in category_articles:
                    summary = self._summarize_article(article)
                    summaries.append(summary)
                    progress.advance(task, 1)
                
                sections.append(ShowNotesSection(
                    title=category,
                    articles=summaries,
                ))
        
        # Create show notes
        show_notes = ShowNotes(
            run_date=run_date,
            sections=sections,
            total_articles=len(articles),
            generation_timestamp=pendulum.now().to_iso8601_string(),
        )
        
        # Get LLM usage stats
        llm_stats = self.llm_provider.get_usage_stats()
        
        # Create generation stats
        stats = GenerationStats(
            articles_processed=len(articles),
            tokens_used=llm_stats.get("total_tokens", 0),
            api_calls=llm_stats.get("api_calls", 0),
            cost_estimate=llm_stats.get("estimated_cost", 0.0),
            processing_time=time.time() - start_time,
        )
        
        return show_notes, stats

    def format_as_markdown(self, show_notes: ShowNotes) -> str:
        """Format show notes as Markdown."""
        lines = []
        
        # Header
        lines.append(f"# AI News Briefing - {show_notes.run_date}")
        lines.append("")
        lines.append(f"*Generated on {pendulum.parse(show_notes.generation_timestamp).format('MMM DD, YYYY [at] HH:mm')} UTC*")
        lines.append("")
        lines.append(f"**{show_notes.total_articles} stories** across {len(show_notes.sections)} categories")
        lines.append("")
        
        # Table of contents
        if len(show_notes.sections) > 1:
            lines.append("## Contents")
            lines.append("")
            for section in show_notes.sections:
                lines.append(f"- [{section.title}](#{section.title.lower().replace(' ', '-').replace('&', 'and')})")
            lines.append("")
        
        # Sections
        for section in show_notes.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            
            for article in section.articles:
                lines.append(f"### [{article.title}]({article.url})")
                lines.append(f"*{article.outlet} • {article.published_date}*")
                lines.append("")
                
                for bullet in article.bullet_points:
                    lines.append(f"- {bullet}")
                lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*This briefing was generated automatically by AI Podcast Agent.*")
        lines.append("")
        
        return "\n".join(lines)


def save_show_notes(show_notes: ShowNotes, output_path: Path) -> None:
    """Save show notes to markdown file."""
    generator = ShowNotesGenerator(None, None)  # Just for formatting
    markdown_content = generator.format_as_markdown(show_notes)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_content, encoding="utf-8")
    
    console.print(f"[green]✓ Show notes saved: {output_path}[/green]")