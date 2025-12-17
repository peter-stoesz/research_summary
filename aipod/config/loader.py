"""Configuration loader."""

import os
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import ValidationError

from .models import ConfigModel, SourceConfig


class Config:
    """Configuration manager."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize config manager."""
        if config_path is None:
            config_path = Path.home() / ".config" / "aipod" / "config.yaml"
        self.config_path = config_path
        self._config: Optional[ConfigModel] = None

    @property
    def config(self) -> ConfigModel:
        """Get loaded config."""
        if self._config is None:
            self._config = load_config(self.config_path)
        return self._config

    @property
    def workspace_root(self) -> Path:
        """Get workspace root path."""
        path = Path(self.config.workspace_root).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_run_dir(self, run_date: str) -> Path:
        """Get run directory path."""
        run_dir = self.workspace_root / "runs" / run_date
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_dir

    def get_db_config(self) -> Dict[str, any]:
        """Get database configuration dict."""
        db_config = self.config.postgres.model_dump()
        
        # Handle password from environment if specified
        if db_config.get("password_env"):
            password = os.environ.get(db_config["password_env"])
            if password:
                db_config["password"] = password
        
        return db_config

    def get_llm_config(self) -> Dict[str, any]:
        """Get LLM configuration dict."""
        llm_config = self.config.llm.model_dump()
        
        # Handle API key from environment if specified
        if llm_config.get("api_key_env"):
            api_key = os.environ.get(llm_config["api_key_env"])
            if api_key:
                llm_config["api_key"] = api_key
                
        return llm_config


def load_config(config_path: Path) -> ConfigModel:
    """Load configuration from YAML file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with open(config_path) as f:
            config_data = yaml.safe_load(f)
            
        if config_data is None:
            config_data = {}
            
        return ConfigModel(**config_data)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")
    except ValidationError as e:
        raise ValueError(f"Invalid configuration: {e}")


def load_sources(sources_path: Path) -> List[SourceConfig]:
    """Load sources from YAML file."""
    if not sources_path.exists():
        raise FileNotFoundError(f"Sources file not found: {sources_path}")

    try:
        with open(sources_path) as f:
            sources_data = yaml.safe_load(f)
            
        if sources_data is None or "sources" not in sources_data:
            return []
            
        sources = []
        for source_data in sources_data["sources"]:
            try:
                sources.append(SourceConfig(**source_data))
            except ValidationError as e:
                print(f"Skipping invalid source {source_data.get('name', 'unknown')}: {e}")
                
        return sources
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in sources file: {e}")


def save_config(config: ConfigModel, config_path: Path) -> None:
    """Save configuration to YAML file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, sort_keys=False)


def save_sources(sources: List[SourceConfig], sources_path: Path) -> None:
    """Save sources to YAML file."""
    sources_path.parent.mkdir(parents=True, exist_ok=True)
    
    sources_data = {"sources": [s.model_dump() for s in sources]}
    
    with open(sources_path, "w") as f:
        yaml.dump(sources_data, f, default_flow_style=False, sort_keys=False)