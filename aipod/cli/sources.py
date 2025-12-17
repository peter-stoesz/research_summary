"""Sources management commands."""

from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.table import Table

from ..config import Config, SourceConfig, load_sources, save_sources

console = Console()
sources_app = typer.Typer(help="Manage RSS sources")


@sources_app.command("list")
def sources_list() -> None:
    """List all configured sources."""
    config = Config()
    sources_path = config.config_path.parent / "sources.yaml"
    
    try:
        sources = load_sources(sources_path)
    except FileNotFoundError:
        console.print("[red]Sources file not found. Run 'aipod init' first.[/red]")
        raise typer.Exit(1)
    
    if not sources:
        console.print("[yellow]No sources configured.[/yellow]")
        return
    
    # Create table
    table = Table(title="Configured Sources")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Weight", style="green")
    table.add_column("Enabled", style="yellow")
    table.add_column("URL", style="blue")
    
    for source in sources:
        table.add_row(
            source.name,
            source.category,
            f"{source.weight:.1f}",
            "✓" if source.enabled else "✗",
            source.url,
        )
    
    console.print(table)


@sources_app.command("add")
def sources_add(
    name: str = typer.Option(..., "--name", "-n", help="Source name"),
    url: str = typer.Option(..., "--url", "-u", help="RSS feed URL"),
    category: str = typer.Option(
        "implementations",
        "--category",
        "-c",
        help="Source category (implementations, concepts, research)",
    ),
    weight: float = typer.Option(
        1.0,
        "--weight",
        "-w",
        help="Source weight (0.0-1.0)",
        min=0.0,
        max=1.0,
    ),
) -> None:
    """Add a new RSS source."""
    config = Config()
    sources_path = config.config_path.parent / "sources.yaml"
    
    try:
        sources = load_sources(sources_path)
    except FileNotFoundError:
        sources = []
    
    # Check if source already exists
    if any(s.name == name or s.url == url for s in sources):
        console.print(f"[red]Source '{name}' or URL already exists.[/red]")
        raise typer.Exit(1)
    
    # Create new source
    new_source = SourceConfig(
        name=name,
        url=url,
        category=category,
        weight=weight,
        enabled=True,
    )
    
    sources.append(new_source)
    save_sources(sources, sources_path)
    
    console.print(f"[green]✅ Added source: {name}[/green]")


@sources_app.command("remove")
def sources_remove(
    name: str = typer.Argument(..., help="Source name to remove"),
) -> None:
    """Remove a source."""
    config = Config()
    sources_path = config.config_path.parent / "sources.yaml"
    
    try:
        sources = load_sources(sources_path)
    except FileNotFoundError:
        console.print("[red]Sources file not found.[/red]")
        raise typer.Exit(1)
    
    # Find and remove source
    original_count = len(sources)
    sources = [s for s in sources if s.name != name]
    
    if len(sources) == original_count:
        console.print(f"[red]Source '{name}' not found.[/red]")
        raise typer.Exit(1)
    
    save_sources(sources, sources_path)
    console.print(f"[green]✅ Removed source: {name}[/green]")


@sources_app.command("test")
def sources_test(
    name: Optional[str] = typer.Argument(None, help="Source name to test (or test all)"),
) -> None:
    """Test RSS feed connectivity."""
    config = Config()
    sources_path = config.config_path.parent / "sources.yaml"
    
    try:
        sources = load_sources(sources_path)
    except FileNotFoundError:
        console.print("[red]Sources file not found.[/red]")
        raise typer.Exit(1)
    
    # Filter sources if name provided
    if name:
        sources = [s for s in sources if s.name == name]
        if not sources:
            console.print(f"[red]Source '{name}' not found.[/red]")
            raise typer.Exit(1)
    
    # Test each source
    with httpx.Client(timeout=10.0) as client:
        for source in sources:
            if not source.enabled:
                console.print(f"[yellow]⚠️  {source.name}: Disabled[/yellow]")
                continue
                
            try:
                response = client.get(source.url)
                response.raise_for_status()
                console.print(f"[green]✅ {source.name}: OK ({response.status_code})[/green]")
            except httpx.HTTPError as e:
                console.print(f"[red]❌ {source.name}: Failed - {e}[/red]")
            except Exception as e:
                console.print(f"[red]❌ {source.name}: Error - {e}[/red]")