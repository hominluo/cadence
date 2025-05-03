"""
Notion Pages API interactions.
"""
from typing import Any, Dict, List, Optional
import httpx
import structlog
from datetime import datetime

logger = structlog.get_logger()

class PagesAPI:
    """
    Handles interactions with Notion's Pages API endpoints.
    Supports page creation, updates, and property management.
    """
    
    def __init__(self, client: httpx.AsyncClient):
        """
        Initialize PagesAPI with an HTTP client.
        
        Args:
            client: Configured httpx AsyncClient for Notion API requests
        """
        self._client = client
        self._log = logger.bind(module="pages_api")

    async def create_page(
        self,
        parent_id: str,
        properties: Dict[str, Any],
        children: Optional[List[Dict[str, Any]]] = None,
        is_database: bool = True
    ) -> Dict[str, Any]:
        """
        Create a new page.
        
        Args:
            parent_id: Parent database or page ID
            properties: Page properties
            children: Initial page content blocks
            is_database: Whether parent is a database
            
        Returns:
            Created page object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            parent_type = "database_id" if is_database else "page_id"
            body = {
                "parent": {
                    "type": parent_type,
                    parent_type: parent_id
                },
                "properties": properties
            }
            
            if children:
                body["children"] = children
                
            response = await self._client.post(
                "pages",
                json=body
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "create_page_error",
                parent_id=parent_id,
                error=str(e)
            )
            raise

    def create_todo_properties(
        self,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create properties for a todo page.
        
        Args:
            title: Todo title
            description: Detailed description
            due_date: When the todo is due
            priority: Priority level
            tags: Category tags
            status: Current status
            
        Returns:
            Properties object for page creation
        """
        properties: Dict[str, Any] = {
            "Task": {
                "title": [{
                    "type": "text",
                    "text": {"content": title}
                }]
            }
        }
        
        if description:
            properties["Description"] = {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": description}
                }]
            }
            
        if due_date:
            properties["Due Date"] = {
                "date": {
                    "start": due_date.isoformat()
                }
            }
            
        if priority:
            properties["Priority"] = {
                "select": {"name": priority}
            }
            
        if tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in tags]
            }
            
        if status:
            properties["Status"] = {
                "status": {"name": status}
            }
            
        return properties

    async def update_page(
        self,
        page_id: str,
        properties: Optional[Dict[str, Any]] = None,
        archived: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update a page's properties or archive status.
        
        Args:
            page_id: Page to update
            properties: Updated properties
            archived: Whether to archive the page
            
        Returns:
            Updated page object
            
        Raises:
            ValueError: If neither properties nor archived is provided
            httpx.HTTPError: On API request failure
        """
        if properties is None and archived is None:
            raise ValueError("Must provide either properties or archived status")
            
        try:
            body: Dict[str, Any] = {}
            
            if properties:
                body["properties"] = properties
            if archived is not None:
                body["archived"] = archived
                
            response = await self._client.patch(
                f"pages/{page_id}",
                json=body
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "update_page_error",
                page_id=page_id,
                error=str(e)
            )
            raise

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Retrieve a page.
        
        Args:
            page_id: Page to retrieve
            
        Returns:
            Page object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.get(f"pages/{page_id}")
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_page_error",
                page_id=page_id,
                error=str(e)
            )
            raise

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """
        Archive a page.
        
        Args:
            page_id: Page to archive
            
        Returns:
            Archived page object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        return await self.update_page(page_id, archived=True)

    async def restore_page(self, page_id: str) -> Dict[str, Any]:
        """
        Restore an archived page.
        
        Args:
            page_id: Page to restore
            
        Returns:
            Restored page object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        return await self.update_page(page_id, archived=False)

    async def get_property_item(
        self,
        page_id: str,
        property_id: str,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Retrieve a page property item.
        
        Args:
            page_id: Page containing property
            property_id: Property to retrieve
            page_size: Number of items for paginated properties (must be positive)
            
        Returns:
            Property item object
            
        Raises:
            ValueError: If page_size is not positive
            httpx.HTTPError: On API request failure
        """
        if page_size <= 0:
            raise ValueError("page_size must be positive")
            
        try:
            response = await self._client.get(
                f"pages/{page_id}/properties/{property_id}",
                params={"page_size": page_size}
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_property_error",
                page_id=page_id,
                property_id=property_id,
                error=str(e)
            )
            raise