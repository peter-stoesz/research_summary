"""Init command implementation."""

from pathlib import Path
from typing import List

import typer
from rich.console import Console
from rich.panel import Panel

from ..config import ConfigModel, SourceConfig, save_config, save_sources
from ..db import init_database, validate_connection

console = Console()


def create_default_sources() -> List[SourceConfig]:
    """Create default AI news sources."""
    return [
        SourceConfig(
            name="Import AI",
            url="https://importai.substack.com/feed",
            category="implementations",
            weight=1.0,
            enabled=True,
        ),
        SourceConfig(
            name="OpenAI Blog",
            url="https://openai.com/blog/rss",
            category="concepts",
            weight=1.0,
            enabled=True,
        ),
        SourceConfig(
            name="Google AI Blog",
            url="https://ai.googleblog.com/feeds/posts/default",
            category="research",
            weight=0.9,
            enabled=True,
        ),
        SourceConfig(
            name="The Information - AI",
            url="https://www.theinformation.com/feed",
            category="implementations",
            weight=0.9,
            enabled=True,
        ),
        SourceConfig(
            name="Anthropic Blog",
            url="https://www.anthropic.com/rss.xml",
            category="concepts",
            weight=1.0,
            enabled=True,
        ),
        SourceConfig(
            name="Hugging Face Blog",
            url="https://huggingface.co/blog/feed.xml",
            category="implementations",
            weight=0.9,
            enabled=True,
        ),
        SourceConfig(
            name="MIT News - AI",
            url="https://news.mit.edu/rss/topic/artificial-intelligence2",
            category="research",
            weight=0.8,
            enabled=True,
        ),
        SourceConfig(
            name="VentureBeat AI",
            url="https://feeds.feedburner.com/venturebeat/SZYF",
            category="implementations",
            weight=0.8,
            enabled=True,
        ),
    ]


def init_command(
    config_dir: Path = typer.Option(
        Path.home() / ".config" / "aipod",
        "--config-dir",
        "-c",
        help="Configuration directory",
    ),
    workspace: Path = typer.Option(
        Path.home() / "AI-Podcast",
        "--workspace",
        "-w",
        help="Workspace root directory",
    ),
    db_host: str = typer.Option("localhost", "--db-host", help="Postgres host"),
    db_port: int = typer.Option(5432, "--db-port", help="Postgres port"),
    db_name: str = typer.Option("aipod", "--db-name", help="Database name"),
    db_user: str = typer.Option("aipod_user", "--db-user", help="Database user"),
    seed_sources: bool = typer.Option(
        True,
        "--seed-sources/--no-seed-sources",
        help="Seed default AI news sources",
    ),
) -> None:
    """Initialize AI Podcast Agent configuration and database."""
    console.print(Panel.fit("🎙️ AI Podcast Agent - Initialization", style="bold blue"))

    # Create configuration directory
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    sources_path = config_dir / "sources.yaml"

    # Create default configuration
    config = ConfigModel(
        workspace_root=str(workspace),
        postgres={
            "host": db_host,
            "port": db_port,
            "database": db_name,
            "user": db_user,
            "password_env": "AIPOD_DB_PASSWORD",
        },
    )

    # Save configuration
    save_config(config, config_path)
    console.print(f"✅ Created config: {config_path}")

    # Create sources file
    if seed_sources:
        sources = create_default_sources()
        save_sources(sources, sources_path)
        console.print(f"✅ Created sources: {sources_path} (seeded with {len(sources)} sources)")
    else:
        save_sources([], sources_path)
        console.print(f"✅ Created sources: {sources_path} (empty)")

    # Create workspace directory
    workspace.mkdir(parents=True, exist_ok=True)
    console.print(f"✅ Created workspace: {workspace}")

    # Validate database connection
    console.print("\n[bold]Testing database connection...[/bold]")
    db_config = config.postgres.model_dump()
    
    if not validate_connection(db_config):
        console.print(
            "[red]❌ Database connection failed![/red]\n"
            "Please ensure Postgres is running and credentials are correct.\n"
            f"Set the password via environment variable: [bold]export AIPOD_DB_PASSWORD=your_password[/bold]"
        )
        raise typer.Exit(1)
    
    console.print("✅ Database connection successful")

    # Initialize database schema
    console.print("\n[bold]Initializing database schema...[/bold]")
    try:
        init_database(db_config)
        console.print("✅ Database schema initialized")
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize database: {e}[/red]")
        raise typer.Exit(1)

    # Success message
    console.print(
        Panel(
            f"[green]✅ AI Podcast Agent initialized successfully![/green]\n\n"
            f"Configuration: {config_path}\n"
            f"Sources: {sources_path}\n"
            f"Workspace: {workspace}\n\n"
            f"Next steps:\n"
            f"1. Set database password: [bold]export AIPOD_DB_PASSWORD=your_password[/bold]\n"
            f"2. Set LLM API key: [bold]export OPENAI_API_KEY=your_key[/bold]\n"
            f"3. Run: [bold]aipod run[/bold]",
            style="green",
        )
    )