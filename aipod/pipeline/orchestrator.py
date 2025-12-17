"""Pipeline orchestrator that runs the complete AI podcast generation pipeline."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pendulum
from psycopg import Connection
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from ..config import Config, load_sources
from ..db import get_connection
from ..db.articles import ArticleStorage
from ..db.runs import RunManager
from ..db.sources import SourceManager
from ..generation import (
    MockLLMProvider,
    OpenAIProvider,
    ScriptGenerator,
    ShowNotesGenerator,
    save_script,
    save_show_notes,
)
from ..generation.script import save_tts_script, create_tts_filename
from ..ingestion import ArticleFetcher, RSSFetcher
from ..ranking import ArticleRanker

console = Console()


class PipelineStage:
    """Represents a pipeline stage."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.success = False
        self.error: Optional[str] = None
        self.stats: Dict = {}

    def start(self):
        """Mark stage as started."""
        self.start_time = time.time()

    def complete(self, stats: Optional[Dict] = None):
        """Mark stage as completed successfully."""
        self.end_time = time.time()
        self.success = True
        if stats:
            self.stats.update(stats)

    def fail(self, error: str):
        """Mark stage as failed."""
        self.end_time = time.time()
        self.success = False
        self.error = error

    @property
    def duration(self) -> float:
        """Get stage duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0


class PipelineOrchestrator:
    """Orchestrates the complete AI podcast generation pipeline."""

    def __init__(self, config: Config):
        """Initialize pipeline orchestrator."""
        self.config = config
        self.stages = [
            PipelineStage("sources", "Loading and syncing sources"),
            PipelineStage("rss", "Fetching RSS feeds"),
            PipelineStage("articles", "Fetching and extracting articles"),
            PipelineStage("storage", "Storing articles and deduplication"),
            PipelineStage("ranking", "Ranking articles by relevance"),
            PipelineStage("show_notes", "Generating show notes"),
            PipelineStage("script", "Generating narration script"),
        ]
        self.run_id: Optional[int] = None
        self.total_start_time: Optional[float] = None

    def _get_llm_provider(self):
        """Get configured LLM provider."""
        llm_config = self.config.get_llm_config()
        
        if llm_config.get("provider") == "openai":
            api_key = llm_config.get("api_key")
            if not api_key:
                console.print("[yellow]Warning: No OpenAI API key found. Using mock LLM provider.[/yellow]")
                return MockLLMProvider()
            
            return OpenAIProvider(
                api_key=api_key,
                model=llm_config.get("model", "gpt-4o-mini"),
                base_url=llm_config.get("base_url"),
            )
        else:
            console.print("[yellow]Warning: Unknown LLM provider. Using mock provider.[/yellow]")
            return MockLLMProvider()

    def _create_run_artifacts_dir(self, run_date: str) -> Path:
        """Create and return run artifacts directory."""
        run_dir = self.config.get_run_dir(run_date)
        
        # Create subdirectories
        (run_dir / "extracted").mkdir(exist_ok=True)
        
        return run_dir

    def _save_stage_stats(self, run_dir: Path):
        """Save pipeline stage statistics."""
        stats = {
            "pipeline": {
                "total_duration": time.time() - self.total_start_time if self.total_start_time else 0,
                "completed_at": datetime.now().isoformat(),
            },
            "stages": {}
        }
        
        for stage in self.stages:
            stats["stages"][stage.name] = {
                "duration": stage.duration,
                "success": stage.success,
                "error": stage.error,
                "stats": stage.stats,
            }
        
        stats_file = run_dir / "pipeline_stats.json"
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=2)

    def _print_summary(self, run_date: str, run_dir: Path):
        """Print pipeline execution summary."""
        successful_stages = sum(1 for s in self.stages if s.success)
        total_duration = time.time() - self.total_start_time if self.total_start_time else 0
        
        # Create summary table
        table = Table(title="Pipeline Summary")
        table.add_column("Stage", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Duration", style="yellow")
        table.add_column("Details", style="dim")
        
        for stage in self.stages:
            status = "[green]✓[/green]" if stage.success else "[red]✗[/red]"
            duration = f"{stage.duration:.1f}s" if stage.duration > 0 else "-"
            
            details = ""
            if stage.success and stage.stats:
                if stage.name == "rss":
                    details = f"{stage.stats.get('total_feeds', 0)} feeds, {stage.stats.get('total_items', 0)} items"
                elif stage.name == "articles":
                    details = f"{stage.stats.get('successful', 0)} articles fetched"
                elif stage.name == "storage":
                    details = f"{stage.stats.get('new', 0)} new, {stage.stats.get('duplicates', 0)} duplicates"
                elif stage.name == "ranking":
                    details = f"{stage.stats.get('selected', 0)} stories selected"
                elif stage.name in ["show_notes", "script"]:
                    details = f"{stage.stats.get('tokens_used', 0)} tokens, ${stage.stats.get('cost_estimate', 0):.3f}"
            elif not stage.success:
                details = stage.error or "Failed"
            
            table.add_row(stage.name.title(), status, duration, details)
        
        console.print("\n")
        console.print(table)
        
        # Final summary
        if successful_stages == len(self.stages):
            console.print(Panel(
                f"[green]✅ Pipeline completed successfully![/green]\n\n"
                f"Run date: {run_date}\n"
                f"Duration: {total_duration:.1f} seconds\n"
                f"Output directory: {run_dir}\n\n"
                f"Generated files:\n"
                f"• show_notes.md\n"
                f"• script.txt\n"
                f"• script_tts_{{timestamp}}.txt\n"
                f"• pipeline_stats.json",
                style="green"
            ))
        else:
            failed_stages = [s.name for s in self.stages if not s.success]
            console.print(Panel(
                f"[red]❌ Pipeline failed![/red]\n\n"
                f"Failed stages: {', '.join(failed_stages)}\n"
                f"Duration: {total_duration:.1f} seconds\n"
                f"Check logs for details.",
                style="red"
            ))

    def run(
        self,
        run_date: str,
        target_minutes: int,
        max_items: int,
        max_stories: int,
    ) -> bool:
        """
        Run the complete pipeline.
        
        Returns:
            True if pipeline completed successfully, False otherwise
        """
        self.total_start_time = time.time()
        
        console.print(Panel.fit(
            f"🎙️ AI Podcast Agent Pipeline\n"
            f"Date: {run_date} • Target: {target_minutes} min • Max stories: {max_stories}",
            style="bold blue"
        ))
        
        # Create run artifacts directory
        run_dir = self._create_run_artifacts_dir(run_date)
        
        # Connect to database
        db_config = self.config.get_db_config()
        
        try:
            with get_connection(db_config) as conn:
                # Create run record
                run_manager = RunManager()
                self.run_id = run_manager.create_run(conn, run_date)
                
                success = self._execute_pipeline(
                    conn, run_date, target_minutes, max_items, max_stories, run_dir
                )
                
                # Update run status
                final_stats = {
                    "target_minutes": target_minutes,
                    "max_items": max_items,
                    "max_stories": max_stories,
                    "total_duration": time.time() - self.total_start_time,
                    "stages": {s.name: s.success for s in self.stages}
                }
                
                run_manager.update_run_status(
                    conn,
                    self.run_id,
                    "success" if success else "failed",
                    final_stats
                )
                
                return success
                
        except Exception as e:
            console.print(f"[red]Database error: {e}[/red]")
            return False
        finally:
            # Save stats and print summary
            self._save_stage_stats(run_dir)
            self._print_summary(run_date, run_dir)

    def _execute_pipeline(
        self,
        conn: Connection,
        run_date: str,
        target_minutes: int,
        max_items: int,
        max_stories: int,
        run_dir: Path,
    ) -> bool:
        """Execute the pipeline stages."""
        
        # Initialize variables that will be passed between stages
        enabled_sources = []
        source_map = {}
        all_items = []
        articles = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            
            # Stage 1: Load and sync sources
            stage = self.stages[0]
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                sources_path = self.config.config_path.parent / "sources.yaml"
                sources = load_sources(sources_path)
                enabled_sources = [s for s in sources if s.enabled]
                
                source_manager = SourceManager()
                source_map = source_manager.sync_sources(conn, sources)
                
                stage.complete({"total_sources": len(sources), "enabled_sources": len(enabled_sources)})
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 2: Fetch RSS feeds
            stage = self.stages[1]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                rss_fetcher = RSSFetcher()
                feed_results = rss_fetcher.fetch_feeds_sync(enabled_sources)
                
                # Collect all feed items
                items_per_feed = max(1, max_items // len(enabled_sources))
                for result in feed_results:
                    if result.success:
                        all_items.extend(result.items[:items_per_feed])
                
                # Limit total items
                all_items = all_items[:max_items]
                
                # Validate we have items to process
                if not all_items:
                    stage.fail("No articles found in RSS feeds")
                    return False
                
                # Set source IDs
                for item in all_items:
                    item.source_id = source_map.get(item.source_name)
                
                stage.complete({
                    "total_feeds": len(feed_results),
                    "successful_feeds": sum(1 for r in feed_results if r.success),
                    "total_items": len(all_items)
                })
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 3: Fetch articles
            stage = self.stages[2]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                article_fetcher = ArticleFetcher()
                articles = article_fetcher.fetch_articles_sync(all_items)
                
                stage.complete({
                    "total_articles": len(articles),
                    "successful": sum(1 for a in articles if a.fetch_success),
                    "failed": sum(1 for a in articles if not a.fetch_success)
                })
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 4: Store articles
            stage = self.stages[3]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                storage = ArticleStorage(self.config.workspace_root)
                storage_stats = storage.process_articles(
                    conn, articles, source_map, self.run_id, run_date
                )
                
                stage.complete(storage_stats)
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 5: Rank articles
            stage = self.stages[4]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                ranker = ArticleRanker(
                    config=self.config.config.ranking,
                    workspace_root=self.config.workspace_root,
                    preferences=self.config.config.preferences.model_dump()
                )
                
                ranking_result = ranker.rank_articles(
                    conn, self.run_id, max_stories=max_stories
                )
                
                stage.complete({
                    "total_articles": ranking_result.total_articles,
                    "selected": len(ranking_result.ranked_articles)
                })
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 6: Generate show notes
            stage = self.stages[5]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                llm_provider = self._get_llm_provider()
                notes_generator = ShowNotesGenerator(llm_provider, self.config.workspace_root)
                
                show_notes, notes_stats = notes_generator.generate_show_notes(
                    conn, self.run_id, run_date
                )
                
                # Save show notes
                notes_path = run_dir / "show_notes.md"
                save_show_notes(show_notes, notes_path)
                
                stage.complete({
                    "articles_processed": notes_stats.articles_processed,
                    "tokens_used": notes_stats.tokens_used,
                    "cost_estimate": notes_stats.cost_estimate
                })
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
            
            # Stage 7: Generate script
            stage = self.stages[6]
            progress.remove_task(task)
            task = progress.add_task(stage.description, total=1)
            stage.start()
            
            try:
                script_generator = ScriptGenerator(llm_provider)
                script, script_stats = script_generator.generate_script(
                    show_notes, target_minutes, run_date
                )
                
                # Save regular script
                script_path = run_dir / "script.txt"
                save_script(script, script_path)
                
                # Save TTS-ready script with timestamp
                tts_filename = create_tts_filename(run_date)
                tts_script_path = run_dir / tts_filename
                save_tts_script(script, tts_script_path)
                
                stage.complete({
                    "estimated_minutes": script.estimated_minutes,
                    "word_count": script.estimated_words,
                    "tokens_used": script_stats.tokens_used,
                    "cost_estimate": script_stats.cost_estimate
                })
                progress.advance(task, 1)
                
            except Exception as e:
                stage.fail(str(e))
                return False
        
        # Check if all stages succeeded
        return all(stage.success for stage in self.stages)