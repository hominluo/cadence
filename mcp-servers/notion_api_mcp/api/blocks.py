"""
Notion Blocks API interactions.
"""
from typing import Any, Dict, List, Optional, Union
import httpx
import structlog
from datetime import datetime
from urllib.parse import urlparse, urlunparse

logger = structlog.get_logger()

class BlocksAPI:
    """
    Handles interactions with Notion's Blocks API endpoints.
    Supports rich text content, formatting, and block operations.
    """
    
    def __init__(self, client: httpx.AsyncClient):
        """
        Initialize BlocksAPI with an HTTP client.
        
        Args:
            client: Configured httpx AsyncClient for Notion API requests
        """
        self._client = client
        self._log = logger.bind(module="blocks_api")

    async def get_block(self, block_id: str) -> Dict[str, Any]:
        """
        Retrieve a block by ID.
        
        Args:
            block_id: ID of the block to retrieve
            
        Returns:
            Block object from Notion API
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.get(f"blocks/{block_id}")
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_block_error",
                block_id=block_id,
                error=str(e)
            )
            raise

    async def append_children(
        self,
        block_id: str,
        blocks: List[Dict[str, Any]],
        after: Optional[str] = None,
        batch_size: int = 100
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Append blocks to a page or existing block with positioning and batch support.
        
        Args:
            block_id: ID of parent block or page
            blocks: List of block objects to append
            after: Optional block ID to append after (for positioning)
            batch_size: Maximum blocks per request (Notion limit is 100)
            
        Returns:
            Single response or list of responses for batched requests
            
        Raises:
            httpx.HTTPError: On API request failure
            ValueError: If batch_size > 100
        """
        if batch_size > 100:
            raise ValueError("batch_size cannot exceed Notion's limit of 100 blocks per request")

        try:
            # Handle large arrays by chunking
            if len(blocks) > batch_size:
                results = []
                for i in range(0, len(blocks), batch_size):
                    batch = blocks[i:i + batch_size]
                    
                    # For batches after first, use last block of previous batch as 'after'
                    batch_after = after if i == 0 else blocks[i - 1].get("id")
                    
                    response = await self._client.patch(
                        f"blocks/{block_id}/children",
                        json={
                            "children": batch,
                            **({"after": batch_after} if batch_after else {})
                        }
                    )
                    response.raise_for_status()
                    result = response.json()
                    results.append(result)
                    
                    # Update after pointer for next batch if needed
                    if result["results"]:
                        after = result["results"][-1]["id"]
                        
                return results

            # Single batch request
            response = await self._client.patch(
                f"blocks/{block_id}/children",
                json={
                    "children": blocks,
                    **({"after": after} if after else {})
                }
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "append_children_error",
                block_id=block_id,
                error=str(e),
                batch_size=batch_size,
                total_blocks=len(blocks)
            )
            raise

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to ensure consistent format.
        Removes trailing slashes and normalizes scheme.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL string
        """
        parsed = urlparse(url)
        # Normalize path by removing trailing slash
        path = parsed.path.rstrip('/')
        # Reconstruct URL with normalized components
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

    def create_block(
        self,
        block_type: str,
        content: Optional[str] = None,
        annotations: Optional[Dict[str, bool]] = None,
        link: Optional[str] = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Create a block of any type with appropriate structure.
        
        Args:
            block_type: Type of block (paragraph, heading_1, divider, etc.)
            content: Optional text content for rich text blocks
            annotations: Optional text formatting for rich text blocks
            link: Optional URL for linked text
            **kwargs: Additional properties specific to block type
            
        Returns:
            Block object for Notion API
        """
        # Special case blocks that don't use rich_text
        if block_type == "divider":
            return {"type": "divider", "divider": {}}
            
        if block_type == "column_list":
            return {"type": "column_list", "column_list": {}}
            
        if block_type == "column":
            return {"type": "column", "column": {}}
            
        # For rich text blocks
        if content is not None:
            text = {"content": content}
            
            if link:
                text["link"] = {"url": self._normalize_url(link)}
                
            rich_text = {
                "type": "text",
                "text": text
            }
            
            if annotations:
                rich_text["annotations"] = annotations
                
            block_content = {"rich_text": [rich_text]}
        else:
            block_content = {}
            
        # Add any additional properties
        block_content.update(kwargs)
            
        return {
            "type": block_type,
            block_type: block_content
        }

    def create_todo_block(
        self,
        content: str,
        checked: bool = False,
        annotations: Optional[Dict[str, bool]] = None,
        is_subtask: bool = False
    ) -> Dict[str, Any]:
        """
        Create a todo block.
        
        Args:
            content: Todo item text
            checked: Whether the todo is completed
            annotations: Text formatting options
            is_subtask: Whether this is a subtask of another todo
            
        Returns:
            Todo block object for Notion API
        """
        text = {
            "type": "text",
            "text": {"content": content}
        }
        
        if annotations:
            text["annotations"] = annotations
            
        return self.create_block(
            "to_do",
            content=content,
            annotations=annotations,
            checked=checked,
            is_subtask=is_subtask
        )

    def create_bulleted_list_block(
        self,
        content: str,
        annotations: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Create a bulleted list item block.
        
        Args:
            content: List item text
            annotations: Text formatting options
            
        Returns:
            Bulleted list block object for Notion API
        """
        return self.create_block(
            "bulleted_list_item",
            content=content,
            annotations=annotations
        )

    def create_rich_text_block(
        self,
        content: str,
        annotations: Optional[Dict[str, bool]] = None,
        link: Optional[str] = None,
        block_type: str = "paragraph"
    ) -> Dict[str, Any]:
        """
        Create a rich text block (paragraph, heading, etc.).
        
        Args:
            content: Text content
            annotations: Text formatting options
            link: Optional URL for linked text
            block_type: Type of text block (paragraph, heading_1, etc.)
            
        Returns:
            Rich text block object for Notion API
        """
        return self.create_block(
            block_type,
            content=content,
            annotations=annotations,
            link=link
        )

    def create_template_block(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """
        DEPRECATED: Template blocks are no longer supported by Notion as of March 27, 2023.
        
        Alternative approaches:
        1. Use database templates instead
        2. Create regular pages with your desired structure
        3. Use the duplicate page functionality
        4. Implement templating logic in your application
        
        Raises:
            NotImplementedError: Always raises this error to prevent usage
        """
        raise NotImplementedError(
            "Template blocks were deprecated by Notion on March 27, 2023. "
            "Please use alternative approaches such as database templates, "
            "regular pages with predefined structure, or implement templating "
            "logic in your application."
        )

    async def get_block_children(
        self,
        block_id: str,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get children blocks of a block.
        
        Args:
            block_id: Parent block ID
            page_size: Number of blocks to return
            start_cursor: Pagination cursor
            
        Returns:
            List of child blocks
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            params = {"page_size": page_size}
            if start_cursor:
                params["start_cursor"] = start_cursor
                
            response = await self._client.get(
                f"blocks/{block_id}/children",
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_block_children_error",
                block_id=block_id,
                error=str(e)
            )
            raise

    async def update_block(
        self,
        block_id: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a block's properties.
        
        Args:
            block_id: Block to update
            properties: New properties
            
        Returns:
            Updated block object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.patch(
                f"blocks/{block_id}",
                json=properties
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "update_block_error",
                block_id=block_id,
                error=str(e)
            )
            raise

    async def delete_block(self, block_id: str) -> Dict[str, Any]:
        """
        Delete a block.
        
        Args:
            block_id: Block to delete
            
        Returns:
            Deleted block object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.delete(f"blocks/{block_id}")
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "delete_block_error",
                block_id=block_id,
                error=str(e)
            )
            raise

    async def create_subtask(
        self,
        parent_id: str,
        content: str,
        checked: bool = False,
        annotations: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Create a subtask under a parent todo.
        
        Args:
            parent_id: ID of parent todo block
            content: Subtask text content
            checked: Whether subtask is completed
            annotations: Text formatting options
            
        Returns:
            Created subtask block
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            # Create subtask block
            subtask = self.create_todo_block(
                content,
                checked,
                annotations,
                is_subtask=True
            )
            
            # Append as child of parent
            response = await self.append_children(parent_id, [subtask])
            self._log.info(
                "created_subtask",
                parent_id=parent_id,
                content=content
            )
            return response
            
        except httpx.HTTPError as e:
            self._log.error(
                "create_subtask_error",
                parent_id=parent_id,
                content=content,
                error=str(e)
            )
            raise

    async def get_subtasks(
        self,
        parent_id: str,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get all subtasks of a todo item.
        
        Args:
            parent_id: ID of parent todo block
            page_size: Number of subtasks to return
            
        Returns:
            List of subtask blocks
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self.get_block_children(
                parent_id,
                page_size=page_size
            )
            
            # Filter for todo blocks marked as subtasks
            subtasks = [
                block for block in response["results"]
                if block["type"] == "to_do" and
                block.get("to_do", {}).get("is_subtask", False)
            ]
            
            self._log.info(
                "got_subtasks",
                parent_id=parent_id,
                count=len(subtasks)
            )
            return subtasks
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_subtasks_error",
                parent_id=parent_id,
                error=str(e)
            )
            raise

    async def update_subtask_status(
        self,
        subtask_id: str,
        checked: bool,
        update_parent: bool = True
    ) -> Dict[str, Any]:
        """
        Update subtask completion status.
        
        Args:
            subtask_id: ID of subtask to update
            checked: New completion status
            update_parent: Whether to update parent status
            
        Returns:
            Updated subtask block
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            # Update subtask status
            await self.update_block(
                subtask_id,
                {"to_do": {"checked": checked}}
            )
            
            if update_parent:
                # Get parent block
                subtask = await self.get_block(subtask_id)
                if parent_id := subtask.get("parent", {}).get("block_id"):
                    # Get all sibling subtasks
                    siblings = await self.get_subtasks(parent_id)
                    
                    # Update parent if all subtasks complete/incomplete
                    all_checked = all(s["to_do"]["checked"] for s in siblings)
                    response = await self.update_block(
                        parent_id,
                        {"to_do": {"checked": all_checked}}
                    )
                    return response
            
            self._log.info(
                "updated_subtask_status",
                subtask_id=subtask_id,
                checked=checked
            )
            return await self.get_block(subtask_id)
            
        except httpx.HTTPError as e:
            self._log.error(
                "update_subtask_status_error",
                subtask_id=subtask_id,
                checked=checked,
                error=str(e)
            )
            raise