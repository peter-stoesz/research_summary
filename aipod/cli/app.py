"""Main CLI application."""

import typer
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

from .init import init_command
from .open import open_command
from .run import run_command
from .sources import sources_app

app = typer.Typer(
    name="aipod",
    help="AI Podcast Agent - Web Scraper and Script Generator",
    no_args_is_help=True,
)

# Register commands
app.command("init")(init_command)
app.command("run")(run_command)
app.command("open")(open_command)
app.add_typer(sources_app, name="sources", help="Manage RSS sources")


if __name__ == "__main__":
    app()