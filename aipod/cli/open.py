"""Open command implementation."""

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from ..config import Config

console = Console()


def open_command(
    latest: bool = typer.Argument(True, help="Open the latest run folder"),
) -> None:
    """Open the latest run folder in Finder."""
    config = Config()
    runs_dir = config.workspace_root / "runs"
    
    if not runs_dir.exists():
        console.print("[red]No runs found. Run 'aipod run' first.[/red]")
        raise typer.Exit(1)
    
    # Find latest run directory
    run_dirs = sorted([d for d in runs_dir.iterdir() if d.is_dir()], reverse=True)
    
    if not run_dirs:
        console.print("[red]No run directories found.[/red]")
        raise typer.Exit(1)
    
    latest_dir = run_dirs[0]
    
    # Open in Finder (macOS)
    if sys.platform == "darwin":
        subprocess.run(["open", str(latest_dir)])
        console.print(f"Opened: {latest_dir}")
    else:
        console.print(f"Latest run: {latest_dir}")
        console.print("[yellow]Note: 'open' command only works on macOS[/yellow]")