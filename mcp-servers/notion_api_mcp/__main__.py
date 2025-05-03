"""Main entry point for notion_api_mcp package."""
import asyncio
from .server import main

if __name__ == "__main__":
    asyncio.run(main())