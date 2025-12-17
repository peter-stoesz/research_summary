"""LLM provider interface and implementations."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import openai
from openai import OpenAI
from rich.console import Console

console = Console()


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def summarize_article(
        self,
        title: str,
        content: str,
        url: str,
        outlet: str,
        max_bullets: int = 4,
    ) -> List[str]:
        """
        Summarize an article into bullet points.
        
        Args:
            title: Article title
            content: Article content
            url: Article URL
            outlet: Publishing outlet
            max_bullets: Maximum number of bullet points
            
        Returns:
            List of bullet point summaries
        """
        pass

    @abstractmethod
    def generate_script(
        self,
        show_notes: str,
        target_minutes: int,
        run_date: str,
    ) -> str:
        """
        Generate a narration script from show notes.
        
        Args:
            show_notes: Formatted show notes content
            target_minutes: Target reading time in minutes
            run_date: Run date for context
            
        Returns:
            Generated script content
        """
        pass

    @abstractmethod
    def get_usage_stats(self) -> Dict:
        """Get usage statistics."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLM provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ) -> None:
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            model: Model name to use
            base_url: Custom base URL (for testing)
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.total_tokens = 0
        self.api_calls = 0
        
        # Token cost estimates (per 1K tokens)
        self.cost_per_1k_tokens = {
            "gpt-4o": {"input": 0.005, "output": 0.015},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4": {"input": 0.03, "output": 0.06},
            "gpt-3.5-turbo": {"input": 0.001, "output": 0.002},
        }

    def _calculate_cost(self, usage: Dict) -> float:
        """Calculate cost from usage statistics."""
        if self.model not in self.cost_per_1k_tokens:
            return 0.0
        
        rates = self.cost_per_1k_tokens[self.model]
        input_cost = (usage.get("prompt_tokens", 0) / 1000) * rates["input"]
        output_cost = (usage.get("completion_tokens", 0) / 1000) * rates["output"]
        
        return input_cost + output_cost

    def summarize_article(
        self,
        title: str,
        content: str,
        url: str,
        outlet: str,
        max_bullets: int = 4,
    ) -> List[str]:
        """Summarize article using OpenAI."""
        # Truncate content if too long (rough token estimate: 1 token ~= 4 chars)
        max_content_chars = 8000  # ~2000 tokens
        if len(content) > max_content_chars:
            content = content[:max_content_chars] + "..."
        
        prompt = f"""Please summarize this AI/technology article into {max_bullets} clear, informative bullet points.

Article Title: {title}
Source: {outlet}
URL: {url}

Article Content:
{content}

Instructions:
- Focus on practical implications, technical details, and business impact
- Each bullet should be 1-2 sentences maximum
- Avoid marketing fluff and focus on concrete developments
- If it's about a product launch, include key capabilities and availability
- If it's research, include key findings and implications
- If it's business news, include scale, partnerships, or strategic implications

Format as a simple bulleted list:
• Point 1
• Point 2
• Point 3
• Point 4 (if applicable)"""

        try:
            self.api_calls += 1
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )
            
            # Update usage stats
            if response.usage:
                self.total_tokens += response.usage.total_tokens
            
            content = response.choices[0].message.content.strip()
            
            # Parse bullets from response
            bullets = []
            for line in content.split('\n'):
                line = line.strip()
                if line and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                    # Remove bullet marker and clean up
                    bullet = line[1:].strip()
                    if bullet:
                        bullets.append(bullet)
            
            # Fallback if no bullets found
            if not bullets:
                bullets = [content]
            
            return bullets[:max_bullets]
            
        except Exception as e:
            console.print(f"[red]Error summarizing article '{title}': {e}[/red]")
            return [f"Failed to summarize: {str(e)}"]

    def generate_script(
        self,
        show_notes: str,
        target_minutes: int,
        run_date: str,
    ) -> str:
        """Generate script using OpenAI."""
        # Estimate target word count (150-180 words per minute for TTS)
        target_words = target_minutes * 160
        
        prompt = f"""Create a podcast script for an AI/technology news briefing based on these show notes.

Show Notes:
{show_notes}

Requirements:
- Target length: approximately {target_words} words ({target_minutes} minutes when read aloud)
- Professional, conversational tone suitable for audio
- Clear transitions between topics
- Start with a brief intro mentioning the date ({run_date}) and what's covered
- End with a short conclusion and mention of show notes availability
- Use natural language that flows well when spoken
- Group related stories together logically
- Reference "show notes" for detailed links, not specific URLs
- Keep paragraphs short for easy reading

Format as a clean script without special formatting or stage directions."""

        try:
            self.api_calls += 1
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=min(target_words + 200, 4000),  # Cap at 4000 tokens
            )
            
            # Update usage stats
            if response.usage:
                self.total_tokens += response.usage.total_tokens
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            console.print(f"[red]Error generating script: {e}[/red]")
            return f"Failed to generate script: {str(e)}"

    def get_usage_stats(self) -> Dict:
        """Get usage statistics."""
        estimated_cost = 0.0
        if self.model in self.cost_per_1k_tokens:
            # Rough estimate (assuming 70% input, 30% output)
            input_tokens = int(self.total_tokens * 0.7)
            output_tokens = int(self.total_tokens * 0.3)
            rates = self.cost_per_1k_tokens[self.model]
            estimated_cost = (
                (input_tokens / 1000) * rates["input"] +
                (output_tokens / 1000) * rates["output"]
            )
        
        return {
            "total_tokens": self.total_tokens,
            "api_calls": self.api_calls,
            "estimated_cost": estimated_cost,
            "model": self.model,
        }


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self) -> None:
        """Initialize mock provider."""
        self.calls = []

    def summarize_article(
        self,
        title: str,
        content: str,
        url: str,
        outlet: str,
        max_bullets: int = 4,
    ) -> List[str]:
        """Mock article summarization."""
        self.calls.append(("summarize", title))
        
        return [
            f"Mock summary of '{title[:50]}...'",
            f"Published by {outlet}",
            "Key technical details and implications",
            "Business impact and next steps",
        ][:max_bullets]

    def generate_script(
        self,
        show_notes: str,
        target_minutes: int,
        run_date: str,
    ) -> str:
        """Mock script generation."""
        self.calls.append(("script", target_minutes))
        
        return f"""Welcome to your AI news briefing for {run_date}.

Today we're covering {target_minutes} minutes of the latest developments in artificial intelligence and technology.

[Mock script content based on show notes]

Our first story covers... [content would be here]

Moving on to our next development... [more content]

That wraps up today's briefing. You can find detailed links and references in the show notes.

Thank you for listening, and we'll see you next time."""

    def get_usage_stats(self) -> Dict:
        """Get mock usage statistics."""
        return {
            "total_tokens": len(self.calls) * 100,
            "api_calls": len(self.calls),
            "estimated_cost": 0.0,
            "model": "mock",
        }