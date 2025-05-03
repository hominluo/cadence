"""
Notion Databases API interactions.
"""
from typing import Any, Dict, List, Optional, Union
import httpx
import structlog
from datetime import datetime

logger = structlog.get_logger()

class DatabasesAPI:
    """
    Handles interactions with Notion's Databases API endpoints.
    Supports advanced querying, filtering, and database management.
    """
    
    def __init__(self, client: httpx.AsyncClient):
        """
        Initialize DatabasesAPI with an HTTP client.
        
        Args:
            client: Configured httpx AsyncClient for Notion API requests
        """
        self._client = client
        self._log = logger.bind(module="databases_api")

    async def create_database(
        self,
        parent_page_id: str,
        title: str,
        properties: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a new database.
        
        Args:
            parent_page_id: ID of parent page
            title: Database title
            properties: Database property definitions
            
        Returns:
            Created database object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.post(
                "databases",
                json={
                    "parent": {
                        "type": "page_id",
                        "page_id": parent_page_id
                    },
                    "title": [{
                        "type": "text",
                        "text": {"content": title}
                    }],
                    "properties": properties
                }
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "create_database_error",
                parent_id=parent_page_id,
                error=str(e)
            )
            raise

    async def query_database(
        self,
        database_id: str,
        filter_conditions: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Query a database with advanced filtering and sorting.
        
        Args:
            database_id: Database to query
            filter_conditions: Filter criteria
            sorts: Sort specifications
            start_cursor: Pagination cursor
            page_size: Results per page
            
        Returns:
            Query results
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            body: Dict[str, Any] = {"page_size": page_size}
            
            if filter_conditions:
                body["filter"] = filter_conditions
            if sorts:
                body["sorts"] = sorts
            if start_cursor:
                body["start_cursor"] = start_cursor
                
            response = await self._client.post(
                f"databases/{database_id}/query",
                json=body
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "query_database_error",
                database_id=database_id,
                error=str(e)
            )
            raise

    def create_filter(
        self,
        conditions: List[Dict[str, Any]],
        operator: str = "and"
    ) -> Dict[str, Any]:
        """
        Create a compound filter for database queries.
        
        Args:
            conditions: List of filter conditions
            operator: Logic operator ('and' or 'or')
            
        Returns:
            Filter object for API
            
        Raises:
            ValueError: If operator is invalid
        """
        if operator not in ("and", "or"):
            raise ValueError("Operator must be 'and' or 'or'")
            
        return {operator: conditions}

    def create_date_filter(
        self,
        property_name: str,
        condition: str,
        value: Union[str, datetime, None] = None
    ) -> Dict[str, Any]:
        """
        Create a date filter condition.
        
        Args:
            property_name: Property to filter on
            condition: Date condition (before, after, equals, etc.)
            value: Date value. If datetime, will be converted to ISO format.
                  If None, used for conditions like 'is_empty'
            
        Returns:
            Date filter object formatted for Notion API
        """
        if isinstance(value, datetime):
            value = value.isoformat()
            
        filter_obj = {
            "property": property_name,
            "date": {}
        }
        
        if value is None and condition in ["is_empty", "is_not_empty"]:
            filter_obj["date"][condition] = True
        else:
            filter_obj["date"][condition] = value
            
        return filter_obj

    def create_text_filter(
        self,
        property_name: str,
        condition: str,
        value: str
    ) -> Dict[str, Any]:
        """
        Create a text filter condition.
        
        Args:
            property_name: Property to filter on
            condition: Text condition (equals, contains, etc.)
            value: Text value
            
        Returns:
            Text filter object
        """
        return {
            "property": property_name,
            "text": {condition: value}
        }

    def create_number_filter(
        self,
        property_name: str,
        condition: str,
        value: Union[int, float]
    ) -> Dict[str, Any]:
        """
        Create a number filter condition.
        
        Args:
            property_name: Property to filter on
            condition: Number condition (equals, greater_than, etc.)
            value: Numeric value
            
        Returns:
            Number filter object
        """
        return {
            "property": property_name,
            "number": {condition: value}
        }

    def create_search_filter(
        self,
        query: str,
        property_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a search filter for full-text or property-specific search.
        
        Args:
            query: Search query text
            property_name: Optional property to search within. If None,
                         performs full-text search across all text content.
            
        Returns:
            Search filter object
        """
        if property_name:
            return {
                "property": property_name,
                "rich_text": {"contains": query}
            }
        else:
            return {"title": {"contains": query}}

    def create_sort(
        self,
        property_name: str,
        direction: str = "ascending"
    ) -> Dict[str, Any]:
        """
        Create a sort specification.
        
        Args:
            property_name: Property to sort by
            direction: Sort direction
            
        Returns:
            Sort object
            
        Raises:
            ValueError: If direction is invalid
        """
        if direction not in ("ascending", "descending"):
            raise ValueError("Direction must be 'ascending' or 'descending'")
            
        return {
            "property": property_name,
            "direction": direction
        }

    async def update_database(
        self,
        database_id: str,
        title: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        archived: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Update database title, schema, or archive status.
        
        Args:
            database_id: Database to update
            title: New title
            properties: Updated property definitions
            archived: Archive status
            
        Returns:
            Updated database object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            body: Dict[str, Any] = {}
            
            if title:
                body["title"] = [{
                    "type": "text",
                    "text": {"content": title}
                }]
                
            if properties:
                body["properties"] = properties
                
            if archived is not None:
                body["archived"] = archived
                
            response = await self._client.patch(
                f"databases/{database_id}",
                json=body
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "update_database_error",
                database_id=database_id,
                error=str(e)
            )
            raise

    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Retrieve database metadata.
        
        Args:
            database_id: Database to retrieve
            
        Returns:
            Database object
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.get(f"databases/{database_id}")
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "get_database_error",
                database_id=database_id,
                error=str(e)
            )
            raise

    async def list_databases(self) -> Dict[str, Any]:
        """
        List all databases the integration has access to.
        
        Returns:
            List of database objects
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            response = await self._client.post(
                "search",
                json={
                    "filter": {
                        "value": "database",
                        "property": "object"
                    }
                }
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPError as e:
            self._log.error(
                "list_databases_error",
                error=str(e)
            )
            raise

    async def search_database(
        self,
        database_id: str,
        query: str,
        property_name: Optional[str] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        start_cursor: Optional[str] = None,
        page_size: int = 100
    ) -> Dict[str, Any]:
        """
        Search database content with optional property-specific search and sorting.
        
        Args:
            database_id: Database to search
            query: Search query text
            property_name: Optional property to search within
            sorts: Optional sort specifications
            start_cursor: Pagination cursor
            page_size: Results per page
            
        Returns:
            Search results from database query
            
        Raises:
            httpx.HTTPError: On API request failure
        """
        try:
            # Create search filter
            filter_obj = self.create_search_filter(query, property_name)
            
            # Query database with filter
            return await self.query_database(
                database_id,
                filter_conditions=filter_obj,
                sorts=sorts,
                start_cursor=start_cursor,
                page_size=page_size
            )
            
        except httpx.HTTPError as e:
            self._log.error(
                "search_database_error",
                database_id=database_id,
                query=query,
                error=str(e)
            )
            raise