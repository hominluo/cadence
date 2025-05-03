"""
Enhanced Notion MCP server implementation.

This module provides a Model Context Protocol (MCP) server that exposes Notion's API
capabilities to Claude. It implements async patterns and proper error handling throughout.

Available Tools:
- add_todo: Add a new todo with rich features
- search_todos: Search todos with advanced filtering
- create_database: Create a new database with custom schema
- query_database: Query database with filters and sorting
- add_content_blocks: Add rich text content blocks
- get_block_content: Get content of blocks
- update_block_content: Update block content
- delete_block: Delete blocks
"""

import httpx
from httpx import AsyncClient
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional, List, Sequence, TypeVar, Callable
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import os
import asyncio
from functools import wraps

from mcp.server.lowlevel import Server as MCPServer
from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import ErrorData, TextContent, EmbeddedResource
from mcp.shared.exceptions import McpError

from .api.pages import PagesAPI
from .api.databases import DatabasesAPI
from .api.blocks import BlocksAPI

# Generic type for return value
T = TypeVar('T')

def with_retry(retry_count: int = 3):
    """Decorator to add retry logic to API calls"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Get self if this is an instance method
            self = args[0] if args else None
            last_error = None
            
            for attempt in range(retry_count):
                try:
                    return await func(*args, **kwargs)
                except McpError:
                    raise  # Don't retry MCP errors
                except Exception as e:
                    last_error = e
                    if attempt < retry_count - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        if self:  # Only call ensure_client if we have an instance
                            await self.ensure_client()  # Ensure fresh client for retry
                        continue
                    
                    # Handle final error
                    if isinstance(e, httpx.HTTPStatusError):
                        if e.response.status_code == 401:
                            raise McpError(ErrorData(
                                code=ErrorCode.AUTHENTICATION_ERROR,
                                message="Invalid authentication token"
                            ))
                        elif e.response.status_code == 404:
                            raise McpError(ErrorData(
                                code=ErrorCode.INVALID_DATABASE,
                                message=f"Resource not found: {str(e)}"
                            ))
                        raise McpError(ErrorData(
                            code=ErrorCode.API_ERROR,
                            message=str(e)
                        ))
                    elif isinstance(e, httpx.RequestError):
                        raise McpError(ErrorData(
                            code=ErrorCode.CONNECTION_ERROR,
                            message=f"Connection error: {str(e)}"
                        ))
                    raise McpError(ErrorData(
                        code=ErrorCode.API_ERROR,
                        message=f"Unexpected error after {retry_count} attempts: {str(e)}"
                    ))
            return last_error
        return wrapper
    return decorator

# Configure logger
logger = logging.getLogger("notion_mcp")

# Error codes
class ErrorCode:
    AUTHENTICATION_ERROR = -32001
    CONNECTION_ERROR = -32002
    INVALID_DATABASE = -32003
    INVALID_BLOCK = -32004
    INVALID_PARAMETERS = -32005
    API_ERROR = -32006

class ServerConfig(BaseModel):
    """Configuration for Notion MCP Server"""
    
    api_key: str = Field(
        description="Notion API integration token",
        alias="NOTION_API_KEY"
    )
    
    database_id: str = Field(
        description="Default todo database ID",
        alias="NOTION_DATABASE_ID"
    )
    
    parent_page_id: str = Field(
        description="Parent page ID for creating new pages",
        alias="NOTION_PARENT_PAGE_ID"
    )
    
    # Note: Template blocks were deprecated by Notion on March 27, 2023
    # Use database templates or regular pages with predefined structure instead
    database_template_id: Optional[str] = Field(
        None,
        description="Database template ID for creating new databases with predefined structure",
        alias="DATABASE_TEMPLATE_ID"
    )

    @classmethod
    def from_env(cls, env_file: str = ".env") -> "ServerConfig":
        """Create config from environment variables"""
        if os.path.exists(env_file):
            load_dotenv(env_file)
            
        return cls(
            NOTION_API_KEY=os.getenv("NOTION_API_KEY", ""),
            NOTION_DATABASE_ID=os.getenv("NOTION_DATABASE_ID", ""),
            NOTION_PARENT_PAGE_ID=os.getenv("NOTION_PARENT_PAGE_ID", ""),
            DATABASE_TEMPLATE_ID=os.getenv("DATABASE_TEMPLATE_ID")
        )

class NotionServer:
    """Notion MCP Server implementation"""
    
    def __init__(self, config: ServerConfig):
        """Initialize the server with configuration"""
        self.logger = logging.getLogger("notion_mcp")
        self.app = FastMCP(
            name="notion-mcp",
            capabilities={
                "notifications": {
                    "progress": True,
                    "initialized": True,
                    "roots_list_changed": True
                }
            }
        )
        self.client = None
        self._config = config
        self.pages_api = None
        self.databases_api = None
        self.blocks_api = None

        # Register tools
        self.register_tools()

    async def ensure_client(self, retry_count: int = 3):
        """Ensure we have a valid client with retry logic"""
        if self.client is None or self.client.is_closed:
            for attempt in range(retry_count):
                try:
                    self.client = AsyncClient(
                        base_url="https://api.notion.com/v1",
                        headers={
                            "Authorization": f"Bearer {self._config.api_key}",
                            "Content-Type": "application/json",
                            "Notion-Version": "2022-06-28"
                        },
                        timeout=30.0,
                        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
                    )
                    # Test connection
                    await self.client.get("/users/me")
                    self.pages_api = PagesAPI(self.client)
                    self.databases_api = DatabasesAPI(self.client)
                    self.blocks_api = BlocksAPI(self.client)
                    break
                except Exception as e:
                    if attempt == retry_count - 1:  # Last attempt
                        raise McpError(ErrorData(
                            code=ErrorCode.CONNECTION_ERROR,
                            message=f"Failed to establish connection after {retry_count} attempts: {str(e)}"
                        ))
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    if self.client:
                        await self.client.aclose()
                        self.client = None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.close()

    async def close(self):
        """Clean up resources"""
        if self.client:
            await self.client.aclose()
            self.client = None

    def register_tools(self):
        """Register all available tools"""

        # Page Management Tools
        @self.app.tool(name="create_page", description="Create a new page in Notion")
        @with_retry(retry_count=3)
        async def handle_create_page(
            parent_id: str,
            properties: Dict[str, Any],
            children: Optional[List[Dict[str, Any]]] = None,
            is_database: bool = True
        ) -> str:
            """Create a new page in Notion"""
            await self.ensure_client()
            try:
                page = await self.pages_api.create_page(
                    parent_id=parent_id,
                    properties=properties,
                    children=children,
                    is_database=is_database
                )
                response = {
                    "success": True,
                    "result": page,
                    "error": None
                }
                return json.dumps(response, indent=2)
            except Exception as e:
                response = {
                    "success": False,
                    "result": None,
                    "error": str(e)
                }
                return json.dumps(response, indent=2)

        @self.app.tool(name="get_page", description="Retrieve a Notion page by its ID")
        @with_retry(retry_count=3)
        async def handle_get_page(page_id: str) -> str:
            """
            Get a page's content and metadata.
            
            Args:
                page_id: The ID of the Notion page to retrieve. This should be a valid
                        Notion page ID in UUID format (e.g., "173dd756-6405-8016-b7e0-dc9aee0a97d6").
                        You can find this ID in the page's URL or use the parent_page_id from config.
            
            Returns:
                JSON string containing the page's metadata and properties
            """
            await self.ensure_client()
            try:
                page = await self.pages_api.get_page(page_id)
                # Return a properly structured response
                response = {
                    "success": True,
                    "result": page,
                    "error": None
                }
                return json.dumps(response, indent=2)
            except Exception as e:
                # Return a properly structured error response
                response = {
                    "success": False,
                    "result": None,
                    "error": str(e)
                }
                return json.dumps(response, indent=2)

        @self.app.tool(name="update_page", description="Update a Notion page")
        @with_retry(retry_count=3)
        async def handle_update_page(
            page_id: str,
            properties: Optional[Dict[str, Any]] = None,
            archived: Optional[bool] = None
        ) -> str:
            """Update a page's properties or archive status"""
            await self.ensure_client()
            try:
                page = await self.pages_api.update_page(
                    page_id=page_id,
                    properties=properties,
                    archived=archived
                )
                response = {
                    "success": True,
                    "result": page,
                    "error": None
                }
                return json.dumps(response, indent=2)
            except Exception as e:
                response = {
                    "success": False,
                    "result": None,
                    "error": str(e)
                }
                return json.dumps(response, indent=2)

        @self.app.tool(name="archive_page", description="Archive a Notion page")
        @with_retry(retry_count=3)
        async def handle_archive_page(page_id: str) -> str:
            """Archive a page"""
            await self.ensure_client()
            page = await self.pages_api.archive_page(page_id)
            return json.dumps(page, indent=2)

        @self.app.tool(name="restore_page", description="Restore an archived Notion page")
        @with_retry(retry_count=3)
        async def handle_restore_page(page_id: str) -> str:
            """Restore an archived page"""
            await self.ensure_client()
            page = await self.pages_api.restore_page(page_id)
            return json.dumps(page, indent=2)

        @self.app.tool(name="get_page_property", description="Get a page property item")
        @with_retry(retry_count=3)
        async def handle_get_property_item(
            page_id: str,
            property_id: str,
            page_size: int = 100
        ) -> str:
            """Get a page's property item"""
            await self.ensure_client()
            property_item = await self.pages_api.get_property_item(
                page_id=page_id,
                property_id=property_id,
                page_size=page_size
            )
            return json.dumps(property_item, indent=2)

        # Todo Tools
        @self.app.tool(name="add_todo", description="Add a new todo with rich features")
        @with_retry(retry_count=3)
        async def handle_add_todo(
            task: str,
            description: Optional[str] = None,
            due_date: Optional[str] = None,
            priority: Optional[str] = None,
            tags: Optional[List[str]] = None
        ) -> str:
            """
            Add a new todo item with rich features.
            
            Args:
                task: The todo task description
                description: Detailed task description with rich text support
                due_date: Due date in ISO format YYYY-MM-DD
                priority: Task priority level (high/medium/low)
                tags: List of tags for categorization
                
            Returns:
                JSON string containing the created todo's details
            """
            await self.ensure_client()
            
            # Parse due date if provided
            parsed_date = None
            if due_date:
                try:
                    parsed_date = datetime.fromisoformat(due_date)
                except ValueError as e:
                    raise McpError(ErrorData(
                        code=ErrorCode.INVALID_PARAMETERS,
                        message=f"Invalid due date format: {str(e)}"
                    ))

            # Create todo properties
            properties = self.pages_api.create_todo_properties(
                title=task,
                description=description,
                due_date=parsed_date,
                priority=priority,
                tags=tags,
                status="Not Started"
            )

            # Create the todo page
            page = await self.pages_api.create_page(
                parent_id=self._config.database_id,
                properties=properties,
                is_database=True
            )

            return json.dumps(page, indent=2)

        @self.app.tool(name="search_todos", description="Search todos with advanced filtering")
        async def handle_search_todos(
            query: str,
            property_name: Optional[str] = None,
            sort_by: Optional[str] = None,
            sort_direction: str = "ascending"
        ) -> str:
            """
            Search todos with advanced filtering.
            
            Args:
                query: Search query text
                property_name: Optional property to search within
                sort_by: Property to sort by
                sort_direction: Sort direction (ascending/descending)
                
            Returns:
                JSON string containing search results
            """
            await self.ensure_client()
            try:
                # Prepare sort specification if provided
                sorts = None
                if sort_by:
                    sorts = [
                        self.databases_api.create_sort(
                            sort_by,
                            sort_direction
                        )
                    ]
                
                # Create search filter
                search_filter = self.databases_api.create_search_filter(
                    query,
                    property_name=property_name
                )
                
                # Execute search
                results = await self.databases_api.query_database(
                    database_id=self._config.database_id,
                    filter_conditions=search_filter,
                    sorts=sorts
                )

                return json.dumps(results, indent=2)

            except McpError:
                raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise McpError(ErrorData(
                        code=ErrorCode.AUTHENTICATION_ERROR,
                        message="Invalid authentication token"
                    ))
                elif e.response.status_code == 404:
                    raise McpError(ErrorData(
                        code=ErrorCode.INVALID_DATABASE,
                        message=f"Database not found: {self._config.database_id}"
                    ))
                raise McpError(ErrorData(
                    code=ErrorCode.API_ERROR,
                    message=str(e)
                ))
            except httpx.RequestError as e:
                raise McpError(ErrorData(
                    code=ErrorCode.CONNECTION_ERROR,
                    message=f"Connection error: {str(e)}"
                ))
            except Exception as e:
                raise McpError(ErrorData(
                    code=ErrorCode.API_ERROR,
                    message=f"Unexpected error: {str(e)}"
                ))

        # Database Operations
        @self.app.tool(name="create_database", description="Create a new database with custom schema in a parent page")
        @with_retry(retry_count=3)
        async def handle_create_database(
            parent_page_id: str,
            title: str,
            properties: Dict[str, Any]
        ) -> str:
            """
            Create a new database with custom schema.
            
            Args:
                parent_page_id: ID of the parent page where the database will be created.
                              IMPORTANT: Must be a Notion page or wiki database that has
                              granted access to your integration. This is a Notion API
                              requirement and cannot be changed after creation.
                title: Database title
                properties: Database property definitions (schema)
                
            Returns:
                JSON string containing the created database object
                
            Raises:
                McpError: If authentication fails or parent page is invalid
                
            Note:
                The parent page must be either a regular Notion page or a wiki database
                that has granted access to your integration. This is a limitation of
                the Notion API and the database location cannot be changed after creation.
            """
            await self.ensure_client()
            database = await self.databases_api.create_database(
                parent_page_id=parent_page_id,
                title=title,
                properties=properties
            )
            return json.dumps(database, indent=2)

        @self.app.tool(name="query_database", description="Query database with filters and sorting")
        @with_retry(retry_count=3)
        async def handle_query_database(
            database_id: str,
            filter_conditions: Optional[Dict[str, Any]] = None,
            sorts: Optional[List[Dict[str, Any]]] = None
        ) -> str:
            """Query database with filters and sorting"""
            await self.ensure_client()
            results = await self.databases_api.query_database(
                database_id=database_id,
                filter_conditions=filter_conditions,
                sorts=sorts
            )
            return json.dumps(results, indent=2)

        # Diagnostic Tools
        @self.app.tool(name="verify_connection", description="Verify authentication with Notion API")
        @with_retry(retry_count=3)
        async def handle_verify_connection() -> str:
            """Test authentication with Notion API"""
            try:
                # First verify we have the required config
                if not self._config.api_key:
                    return json.dumps({
                        "success": False,
                        "result": None,
                        "error": "No API key provided - check NOTION_API_KEY environment variable"
                    }, indent=2)

                # Create a fresh client just for verification
                async with AsyncClient(
                    base_url="https://api.notion.com/v1",
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
                        "Content-Type": "application/json",
                        "Notion-Version": "2022-06-28"
                    },
                    timeout=30.0
                ) as client:
                    # Test authentication by getting current user
                    user_response = await client.get("/users/me")
                    user_response.raise_for_status()
                    user_data = user_response.json()

                    # If we have a database ID, optionally test access
                    database_status = None
                    if self._config.database_id:
                        try:
                            db_response = await client.get(f"/databases/{self._config.database_id}")
                            db_response.raise_for_status()
                            database_status = "accessible"
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                database_status = "not found"
                            else:
                                database_status = "access denied"

                    # Mask API key for safe display (show first 4 and last 4 chars)
                    api_key = self._config.api_key
                    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "invalid_length"
                    
                    # Create a diagnostic message that will be visible in the response
                    diagnostic_info = (
                        "\n=== Configuration Diagnostics ===\n"
                        f"API Key: {masked_key}\n"
                        f"API Key Length: {len(api_key)}\n"
                        f"API Key Format: {'Valid (starts with ntn_)' if api_key.startswith('ntn_') else 'Invalid prefix'}\n"
                        f"Database ID: {self._config.database_id}\n"
                        f"Database Status: {database_status}\n"
                        f"Parent Page ID: {self._config.parent_page_id}\n"
                        "============================\n"
                    )

                    response_data = {
                        "success": True,
                        "result": {
                            "auth_status": "valid",
                            "user": user_data,
                            "api_version": "2022-06-28",
                            "database_status": database_status,
                            "diagnostic_message": diagnostic_info  # Include formatted message in result
                        },
                        "error": None
                    }

                    # Add the diagnostic info as a string property that Claude can display
                    response_data["diagnostic_info"] = diagnostic_info

                    return json.dumps(response_data, indent=2)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    # Create diagnostic info even for error case
                    api_key = self._config.api_key
                    masked_key = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "invalid_length"
                    # Expected format check
                    expected_key = "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"
                    
                    diagnostic_info = (
                        "\n!!! ERROR DIAGNOSTICS !!!\n"
                        f"API Key Being Used: {masked_key}\n"
                        f"First 8 chars: {api_key[:8]}\n"
                        f"Last 8 chars: {api_key[-8:]}\n"
                        f"Key Length: {len(api_key)} chars\n"
                        f"Expected Length: {len(expected_key)} chars\n"
                        f"Extra chars at end: {api_key[len(expected_key):] if len(api_key) > len(expected_key) else 'none'}\n"
                        f"Contains whitespace: {any(c.isspace() for c in api_key)}\n"
                        f"Starts with 'ntn_': {api_key.startswith('ntn_')}\n"
                        f"Database ID: {self._config.database_id}\n"
                        f"Database ID Length: {len(self._config.database_id)} chars\n"
                        "\nPROBLEM DETECTED: Your API key in claude_desktop_config.json has an extra 'x' at the end\n"
                        "Please update the key in: ~/Library/Application Support/Claude/claude_desktop_config.json\n"
                        "!!!!!!!!!!!!!!!!!!!!!!!!\n"
                    )
                    
                    return json.dumps({
                        "success": False,
                        "result": None,
                        "error": f"HELLO CLAUDE! Auth failed - if you see this message, we're editing the right code! Status code: 401\n\n{diagnostic_info}",
                        "diagnostic_info": diagnostic_info
                    }, indent=2)
                return json.dumps({
                    "success": False,
                    "result": None,
                    "error": f"API error: {str(e)}"
                }, indent=2)
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "result": None,
                    "error": f"Unexpected error: {str(e)}"
                }, indent=2)

        @self.app.tool(name="get_database_info", description="Get information about the configured database")
        @with_retry(retry_count=3)
        async def handle_get_database_info() -> str:
            """Get details about the configured database"""
            await self.ensure_client()
            try:
                response = await self.client.get(f"/databases/{self._config.database_id}")
                response.raise_for_status()
                db_data = response.json()
                return json.dumps({
                    "success": True,
                    "result": {
                        "database": db_data,
                        "id": self._config.database_id,
                        "parent": db_data.get("parent", {}),
                        "properties": db_data.get("properties", {})
                    },
                    "error": None
                }, indent=2)
            except Exception as e:
                return json.dumps({
                    "success": False,
                    "result": None,
                    "error": str(e)
                }, indent=2)

        # Block Operations
        @self.app.tool(name="add_content_blocks", description="Add content blocks with positioning support")
        @with_retry(retry_count=3)
        async def handle_add_blocks(
            page_id: str,
            blocks: List[Dict[str, Any]],
            after: Optional[str] = None,
            batch_size: Optional[int] = None
        ) -> str:
            """
            Add content blocks with support for positioning and large arrays.
            
            Args:
                page_id: ID of the parent page/block
                blocks: List of block objects to append
                after: Optional block ID to append after for positioning
                batch_size: Optional maximum blocks per request (default 100)
                
            Returns:
                JSON string containing the API response(s)
            """
            await self.ensure_client()
            try:
                result = await self.blocks_api.append_children(
                    block_id=page_id,
                    blocks=blocks,
                    after=after,
                    batch_size=batch_size or 100
                )
                return json.dumps(result, indent=2)
            except ValueError as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, indent=2)

        @self.app.tool(name="get_block_content", description="Get content of a specific block by its ID")
        @with_retry(retry_count=3)
        async def handle_get_block(
            block_id: str
        ) -> str:
            """
            Get a block's content and metadata.
            
            Args:
                block_id: The ID of the Notion block to retrieve. This should be a valid
                         Notion block ID in UUID format (e.g., "173dd756-6405-8128-97c8-d717fbd3f5fb").
                         You can get block IDs from list_block_children or when creating blocks.
            
            Returns:
                JSON string containing the block's content and metadata
            """
            await self.ensure_client()
            block = await self.blocks_api.get_block(block_id)
            return json.dumps(block, indent=2)

        @self.app.tool(name="list_block_children", description="List all children of a block")
        @with_retry(retry_count=3)
        async def handle_list_block_children(
            block_id: str,
            page_size: int = 100
        ) -> str:
            """List all children blocks of a given block or page"""
            await self.ensure_client()
            children = await self.blocks_api.get_block_children(
                block_id=block_id,
                page_size=page_size
            )
            return json.dumps(children, indent=2)

        @self.app.tool(name="update_block_content", description="Update a block's content by its ID")
        @with_retry(retry_count=3)
        async def handle_update_block(
            block_id: str,
            content: Dict[str, Any]
        ) -> str:
            """
            Update a block's content.
            
            Args:
                block_id: The ID of the Notion block to update. This should be a valid
                         Notion block ID in UUID format (e.g., "173dd756-6405-8128-97c8-d717fbd3f5fb").
                content: The new content for the block. For a paragraph block, use format:
                        {
                            "paragraph": {
                                "rich_text": [{
                                    "text": {
                                        "content": "Your text here"
                                    },
                                    "type": "text"
                                }]
                            }
                        }
            
            Returns:
                JSON string containing the updated block
            """
            await self.ensure_client()
            # For updating block content, we need to pass the content object directly
            block = await self.blocks_api.update_block(
                block_id=block_id,
                properties=content
            )
            return json.dumps(block, indent=2)

        @self.app.tool(name="delete_block", description="Delete blocks")
        @with_retry(retry_count=3)
        async def handle_delete_block(
            block_id: str
        ) -> str:
            """Delete blocks"""
            await self.ensure_client()
            result = await self.blocks_api.delete_block(block_id)
            return json.dumps({"success": True, "block_id": block_id}, indent=2)

        # Resources
        @self.app.resource("notion://todos", mime_type="application/json")
        async def handle_todos_resource() -> str:
            """Raw todos data resource"""
            await self.ensure_client()
            try:
                results = await self.databases_api.query_database(
                    database_id=self._config.database_id
                )
                return json.dumps(results, indent=2)
            except Exception as e:
                self.logger.error(f"Error accessing todos resource: {e}")
                return json.dumps({"error": str(e)}, indent=2)

def create_server():
    """Create and configure the server instance"""
    try:
        server = NotionServer(ServerConfig.from_env())
        return server
    except Exception as e:
        logger.warning(f"Failed to initialize server with environment config: {e}")
        return None

async def main():
    """Main entry point for the enhanced server"""
    server = create_server()
    if server is None:
        logger.error("Failed to initialize server")
        return
        
    async with server:
        try:
            await server.app.run_stdio_async()
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
            raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())