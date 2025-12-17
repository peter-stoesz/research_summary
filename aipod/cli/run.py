"""Run command implementation."""

from datetime import date
from pathlib import Path
from typing import Optional

import pendulum
import typer
from rich.console import Console

from ..config import Config
from ..db import validate_connection
from ..pipeline import PipelineOrchestrator

console = Console()


def run_command(
    run_date: Optional[str] = typer.Option(
        None,
        "--date",
        help="Logical date of the run (YYYY-MM-DD). Default: today",
    ),
    minutes: Optional[int] = typer.Option(
        None,
        "--minutes",
        "-m",
        help="Target read time in minutes",
    ),
    max_items: Optional[int] = typer.Option(
        None,
        "--max-items",
        help="Maximum RSS items to process",
    ),
    max_stories: Optional[int] = typer.Option(
        None,
        "--max-stories",
        help="Maximum stories to include in output",
    ),
) -> None:
    """Run the AI Podcast pipeline to generate show notes and script."""
    try:
        # Load configuration
        config = Config()
        
        # Use defaults from config if not provided
        if run_date is None:
            run_date = pendulum.now().format("YYYY-MM-DD")
        
        if minutes is None:
            minutes = config.config.run_defaults.minutes
        
        if max_items is None:
            max_items = config.config.run_defaults.max_items
        
        if max_stories is None:
            max_stories = config.config.run_defaults.max_stories
        
        # Validate database connection
        console.print("[dim]Checking database connection...[/dim]")
        if not validate_connection(config.get_db_config()):
            console.print("[red]❌ Database connection failed![/red]")
            console.print("Please check your database configuration and ensure Postgres is running.")
            raise typer.Exit(1)
        
        # Run pipeline
        orchestrator = PipelineOrchestrator(config)
        success = orchestrator.run(
            run_date=run_date,
            target_minutes=minutes,
            max_items=max_items,
            max_stories=max_stories,
        )
        
        if not success:
            raise typer.Exit(1)
            
    except KeyboardInterrupt:
        console.print("\n[yellow]Pipeline interrupted by user[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        raise typer.Exit(1)