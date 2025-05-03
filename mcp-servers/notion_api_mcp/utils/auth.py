"""
Authentication and configuration utilities.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

def load_env_file(env_path: Optional[Path] = None) -> None:
    """
    Load environment variables from .env file.
    
    Args:
        env_path: Optional path to .env file. If not provided,
                 searches in project root.
    
    Raises:
        FileNotFoundError: If .env file not found
        ValueError: If required variables are missing
    """
    if env_path is None:
        project_root = Path(__file__).parent.parent.parent.parent
        env_path = project_root / '.env'
    
    if not env_path.exists():
        raise FileNotFoundError(f"No .env file found at {env_path}")
        
    load_dotenv(env_path)
    
    required_vars = ['NOTION_API_KEY', 'NOTION_DATABASE_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

def get_auth_headers(api_key: Optional[str] = None) -> dict:
    """
    Get Notion API authentication headers.
    
    Args:
        api_key: Optional API key. If not provided, uses NOTION_API_KEY
                environment variable.
    
    Returns:
        Dict of headers including authentication
        
    Raises:
        ValueError: If no API key is available
    """
    # Use environment variable if no explicit key provided
    if api_key is None:
        api_key = os.getenv('NOTION_API_KEY')
    
    # Check for missing or empty key
    if not api_key or api_key.strip() == "":
        raise ValueError("No API key provided and NOTION_API_KEY environment variable not set")
        
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

def validate_config() -> None:
    """
    Validate all required configuration is present.
    
    Raises:
        ValueError: If any required configuration is missing
    """
    required_config = {
        'NOTION_API_KEY': os.getenv('NOTION_API_KEY'),
        'NOTION_DATABASE_ID': os.getenv('NOTION_DATABASE_ID')
    }
    
    missing = [key for key, value in required_config.items() if not value or value.strip() == ""]
    
    if missing:
        raise ValueError(f"Missing required configuration: {', '.join(missing)}")
    
    # Only log success if all required config is present
    logger.info("configuration_validated", config_keys=list(required_config.keys()))