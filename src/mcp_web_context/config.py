"""
Configuration management for MCP Web Context.

Handles loading YAML configuration and providing model fallback logic for agents.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import yaml
from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class ModelConfig(BaseModel):
    """Configuration for a single model."""
    provider: str = Field(..., description="Model provider (openai, anthropic, ollama, etc.)")
    model: str = Field(..., description="Model name/identifier")
    api_key_env: Optional[str] = Field(None, description="Environment variable for API key")
    base_url: Optional[str] = Field(None, description="Base URL for API (e.g., for Ollama)")
    temperature: float = Field(0.3, description="Temperature setting for the model")
    reasoning: Optional[Dict[str, Any]] = Field(None, description="Reasoning configuration for OpenAI models")


class AgentConfig(BaseModel):
    """Configuration for an agent including its model fallback list."""
    models: List[ModelConfig] = Field(..., description="List of models to try in order")


class Config(BaseModel):
    """Main configuration object."""
    models: Dict[str, Dict[str, AgentConfig]] = Field(..., description="Model configurations by category and agent")


class ConfigManager:
    """Manages configuration loading and model fallback logic."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file. If None, looks for config.yaml in project root.
        """
        if config_path is None:
            # Find project root by looking for pyproject.toml
            current_dir = Path(__file__).parent
            while current_dir != current_dir.parent:
                if (current_dir / "pyproject.toml").exists():
                    config_path = str(current_dir / "config.yaml")
                    break
                current_dir = current_dir.parent
            else:
                raise FileNotFoundError("Could not find project root with pyproject.toml")
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Config:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
        
        # Parse agents configuration
        agents_config = {}
        if 'models' in raw_config and 'agents' in raw_config['models']:
            for agent_name, agent_data in raw_config['models']['agents'].items():
                agents_config[agent_name] = AgentConfig(**agent_data)
        
        return Config(models={"agents": agents_config})
    
    def get_agent_config(self, agent_name: str) -> Optional[AgentConfig]:
        """Get configuration for a specific agent."""
        return self.config.models.get("agents", {}).get(agent_name)
    
    def get_model_configs(self, agent_name: str) -> List[ModelConfig]:
        """Get list of model configurations for an agent."""
        agent_config = self.get_agent_config(agent_name)
        if agent_config is None:
            return []
        return agent_config.models
    
    def create_llm_instance(self, agent_name: str, model_index: int = 0):
        """
        Create an LLM instance for the specified agent and model index.
        
        Args:
            agent_name: Name of the agent
            model_index: Index in the model list to use
            
        Returns:
            LLM instance or None if failed
        """
        model_configs = self.get_model_configs(agent_name)
        if model_index >= len(model_configs):
            return None
        
        model_config = model_configs[model_index]
        
        try:
            if model_config.provider == "openai":
                from langchain_openai import ChatOpenAI
                from pydantic import SecretStr
                
                api_key = os.getenv(model_config.api_key_env) if model_config.api_key_env else None
                if not api_key:
                    logger.warning(f"API key not found for {model_config.provider}: {model_config.api_key_env}")
                    return None
                
                kwargs = {
                    "model": model_config.model,
                    "api_key": SecretStr(api_key),
                    "temperature": model_config.temperature,
                }
                
                if model_config.reasoning:
                    kwargs["reasoning"] = model_config.reasoning
                    kwargs["output_version"] = "responses/v1"
                
                return ChatOpenAI(**kwargs)
                
            elif model_config.provider == "anthropic":
                from langchain_anthropic import ChatAnthropic
                
                api_key = os.getenv(model_config.api_key_env) if model_config.api_key_env else None
                if not api_key:
                    logger.warning(f"API key not found for {model_config.provider}: {model_config.api_key_env}")
                    return None
                
                return ChatAnthropic(
                    model=model_config.model,
                    api_key=api_key,
                    temperature=model_config.temperature,
                )
                
            elif model_config.provider == "ollama":
                from langchain_ollama import ChatOllama
                
                return ChatOllama(
                    model=model_config.model,
                    base_url=model_config.base_url or "http://localhost:11434",
                    temperature=model_config.temperature,
                )
            
            else:
                logger.error(f"Unsupported provider: {model_config.provider}")
                return None
                
        except Exception as e:
            logger.warning(f"Failed to create LLM for {model_config.provider}/{model_config.model}: {e}")
            return None

    async def get_working_llm(self, agent_name: str) -> Tuple[Any, Optional[ModelConfig]]:
        """
        Try each model in the agent's configuration until one works.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Tuple of (llm_instance, model_config) or (None, None) if all fail
        """
        model_configs = self.get_model_configs(agent_name)
        
        for i, model_config in enumerate(model_configs):
            logger.info(f"Trying model {i+1}/{len(model_configs)}: {model_config.provider}/{model_config.model}")
            
            llm = self.create_llm_instance(agent_name, i)
            if llm is None:
                continue
            
            # Test the model with a simple prompt
            try:
                test_response = await llm.ainvoke("Test")
                logger.info(f"Successfully connected to {model_config.provider}/{model_config.model}")
                return llm, model_config
            except Exception as e:
                logger.warning(f"Model {model_config.provider}/{model_config.model} failed test: {e}")
                continue
        
        logger.error(f"All models failed for agent: {agent_name}")
        return None, None


# Global instance
_config_manager = None


def get_config_manager() -> ConfigManager:
    """Get global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager