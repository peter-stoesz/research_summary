"""Script generator for podcast narration."""

import re
import time
from pathlib import Path
from typing import Optional, Tuple

import pendulum
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from .llm_provider import LLMProvider
from .models import GenerationStats, Script, ShowNotes

console = Console()


class ScriptGenerator:
    """Generate narration-ready scripts from show notes."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        """
        Initialize script generator.
        
        Args:
            llm_provider: LLM provider for script generation
        """
        self.llm_provider = llm_provider

    def _estimate_reading_time(self, text: str) -> Tuple[int, float]:
        """
        Estimate word count and reading time.
        
        Args:
            text: Script text
            
        Returns:
            Tuple of (word_count, estimated_minutes)
        """
        # Remove extra whitespace and count words
        words = len(re.findall(r'\b\w+\b', text))
        
        # Average reading speed for TTS: 150-180 words per minute
        # Use 160 as middle ground
        minutes = words / 160.0
        
        return words, minutes

    def _format_show_notes_for_script(self, show_notes: ShowNotes) -> str:
        """Format show notes content for script generation."""
        lines = []
        
        # Add header info
        lines.append(f"Date: {show_notes.run_date}")
        lines.append(f"Total Articles: {show_notes.total_articles}")
        lines.append("")
        
        # Add each section
        for section in show_notes.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            
            for article in section.articles:
                lines.append(f"**{article.title}** ({article.outlet}, {article.published_date})")
                for bullet in article.bullet_points:
                    lines.append(f"- {bullet}")
                lines.append("")
        
        return "\n".join(lines)

    def generate_script(
        self,
        show_notes: ShowNotes,
        target_minutes: int,
        run_date: Optional[str] = None,
    ) -> Tuple[Script, GenerationStats]:
        """
        Generate a narration script from show notes.
        
        Args:
            show_notes: Show notes to convert to script
            target_minutes: Target reading time in minutes
            run_date: Optional override for run date
            
        Returns:
            Tuple of (script, generation_stats)
        """
        start_time = time.time()
        
        if not run_date:
            run_date = show_notes.run_date
        
        # Format show notes for LLM consumption
        formatted_notes = self._format_show_notes_for_script(show_notes)
        
        # Generate script with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating narration script...", total=1)
            
            script_content = self.llm_provider.generate_script(
                show_notes=formatted_notes,
                target_minutes=target_minutes,
                run_date=run_date,
            )
            
            progress.advance(task, 1)
        
        # Estimate reading time
        word_count, estimated_minutes = self._estimate_reading_time(script_content)
        
        # Create script object
        script = Script(
            run_date=run_date,
            target_minutes=target_minutes,
            content=script_content,
            estimated_words=word_count,
            estimated_minutes=estimated_minutes,
            generation_timestamp=pendulum.now().to_iso8601_string(),
        )
        
        # Get LLM usage stats
        llm_stats = self.llm_provider.get_usage_stats()
        
        # Create generation stats
        stats = GenerationStats(
            articles_processed=show_notes.total_articles,
            tokens_used=llm_stats.get("total_tokens", 0),
            api_calls=llm_stats.get("api_calls", 0),
            cost_estimate=llm_stats.get("estimated_cost", 0.0),
            processing_time=time.time() - start_time,
        )
        
        return script, stats

    def optimize_for_target_length(
        self,
        show_notes: ShowNotes,
        target_minutes: int,
        tolerance_minutes: float = 0.5,
        max_iterations: int = 2,
    ) -> Tuple[Script, GenerationStats]:
        """
        Generate script with length optimization.
        
        Args:
            show_notes: Show notes to convert
            target_minutes: Target reading time
            tolerance_minutes: Acceptable deviation from target
            max_iterations: Maximum optimization attempts
            
        Returns:
            Tuple of (best_script, combined_stats)
        """
        best_script = None
        total_stats = GenerationStats(articles_processed=show_notes.total_articles)
        
        for iteration in range(max_iterations):
            script, stats = self.generate_script(show_notes, target_minutes)
            
            # Combine stats
            total_stats.tokens_used += stats.tokens_used
            total_stats.api_calls += stats.api_calls
            total_stats.cost_estimate += stats.cost_estimate
            total_stats.processing_time += stats.processing_time
            
            # Check if length is acceptable
            length_diff = abs(script.estimated_minutes - target_minutes)
            
            if length_diff <= tolerance_minutes or best_script is None:
                best_script = script
                
                if length_diff <= tolerance_minutes:
                    break
            
            # Adjust target for next iteration
            if script.estimated_minutes > target_minutes:
                target_minutes = max(1, target_minutes - 1)
            else:
                target_minutes += 1
        
        return best_script, total_stats


def save_script(script: Script, output_path: Path) -> None:
    """Save script to text file."""
    lines = []
    
    # Add metadata header
    lines.append(f"# AI News Briefing Script - {script.run_date}")
    lines.append("")
    lines.append(f"Target: {script.target_minutes} minutes")
    lines.append(f"Estimated: {script.estimated_minutes:.1f} minutes ({script.estimated_words} words)")
    lines.append(f"Generated: {pendulum.parse(script.generation_timestamp).format('MMM DD, YYYY [at] HH:mm')} UTC")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Add script content
    lines.append(script.content)
    
    # Save to file
    content = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    
    console.print(f"[green]✓ Script saved: {output_path}[/green]")
    console.print(f"  {script.estimated_words} words, ~{script.estimated_minutes:.1f} minutes")