"""
Utility functions and helpers for Notion API interactions.
"""
from .auth import (
    load_env_file,
    get_auth_headers,
    validate_config
)

from .formatting import (
    create_rich_text,
    create_block,
    format_date,
    parse_markdown_to_blocks,
    blocks_to_markdown,
    format_rich_text_content
)

# Default retry configuration
RETRY_CONFIG = {
    "max_retries": 3,
    "min_delay": 1,  # seconds
    "max_delay": 10,  # seconds
    "exponential_base": 2
}

# Rate limiting configuration
RATE_LIMITS = {
    "max_requests_per_second": 3,
    "max_requests_per_minute": 90
}

# HTTP client configuration
HTTP_CONFIG = {
    "timeout": 30.0,  # seconds
    "max_keepalive_connections": 5,
    "max_connections": 10,
    "retry_config": RETRY_CONFIG
}

__all__ = [
    # Auth utilities
    'load_env_file',
    'get_auth_headers',
    'validate_config',
    
    # Formatting utilities
    'create_rich_text',
    'create_block',
    'format_date',
    'parse_markdown_to_blocks',
    'blocks_to_markdown',
    'format_rich_text_content',
    
    # Configuration
    'RETRY_CONFIG',
    'RATE_LIMITS',
    'HTTP_CONFIG'
]