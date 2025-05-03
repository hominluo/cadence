"""
Pydantic models for Notion API responses.
"""
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from .properties import PropertyValue, PropertySchema

class User(BaseModel):
    """Notion user object."""
    object: Literal["user"]
    id: str
    type: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None

class Parent(BaseModel):
    """Parent object for pages and databases."""
    type: str
    page_id: Optional[str] = None
    database_id: Optional[str] = None
    workspace: Optional[bool] = None

class DatabaseObject(BaseModel):
    """Database object from Notion API."""
    object: Literal["database"]
    id: str
    created_time: datetime
    last_edited_time: datetime
    title: List[dict]
    properties: Dict[str, PropertySchema]
    parent: Parent
    url: str
    archived: bool = False

class PageObject(BaseModel):
    """Page object from Notion API."""
    object: Literal["page"]
    id: str
    created_time: datetime
    last_edited_time: datetime
    created_by: User
    last_edited_by: User
    parent: Parent
    archived: bool
    properties: Dict[str, PropertyValue]
    url: str

class BlockObject(BaseModel):
    """Block object from Notion API."""
    object: Literal["block"]
    id: str
    type: str
    created_time: datetime
    last_edited_time: datetime
    has_children: bool
    archived: bool
    content: Dict[str, Any] = Field(alias="type_content")

    class Config:
        populate_by_name = True

    @property
    def content_type(self) -> str:
        """Get the block's content type."""
        return self.type

class PaginatedList(BaseModel):
    """Base paginated list response."""
    object: Literal["list"]
    next_cursor: Optional[str] = None
    has_more: bool
    type: str

class DatabaseList(PaginatedList):
    """Paginated list of databases."""
    type: Literal["database"]
    results: List[DatabaseObject]

class PageList(PaginatedList):
    """Paginated list of pages."""
    type: Literal["page"]
    results: List[PageObject]

class BlockList(PaginatedList):
    """Paginated list of blocks."""
    type: Literal["block"]
    results: List[BlockObject]

class ErrorResponse(BaseModel):
    """Error response from Notion API."""
    object: Literal["error"]
    status: int
    code: str
    message: str

class SearchResponse(PaginatedList):
    """Search results response."""
    type: Literal["page_or_database"]
    results: List[Dict[str, Any]]  # Can be either page or database

class PropertyItemResponse(BaseModel):
    """Response for property item requests."""
    object: Literal["property_item"]
    id: str
    type: str
    value: Any

class PropertyItemList(PaginatedList):
    """Paginated list of property items."""
    type: Literal["property_item"]
    results: List[PropertyItemResponse]

class TodoResponse(BaseModel):
    """Enhanced todo item response."""
    id: str
    url: str
    task: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    priority: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    status: str = "not_started"
    created_time: datetime
    last_edited_time: datetime
    created_by: str
    last_edited_by: str

    @classmethod
    def from_page_object(cls, page: PageObject) -> "TodoResponse":
        """Create TodoResponse from a Notion page object."""
        properties = page.properties
        
        return cls(
            id=page.id,
            url=page.url,
            task=properties["Task"].value.title[0].text.content
            if "Task" in properties
            else "",
            description=properties["Description"].value.rich_text[0].text.content
            if "Description" in properties and properties["Description"].value.rich_text
            else None,
            due_date=properties["Due Date"].value.date.start
            if "Due Date" in properties and properties["Due Date"].value.date
            else None,
            priority=properties["Priority"].value.select.name
            if "Priority" in properties and properties["Priority"].value.select
            else None,
            tags=[tag.name for tag in properties["Tags"].value.multi_select]
            if "Tags" in properties
            else [],
            status=properties["Status"].value.select.name
            if "Status" in properties and properties["Status"].value.select
            else "not_started",
            created_time=page.created_time,
            last_edited_time=page.last_edited_time,
            created_by=page.created_by.name or page.created_by.id,
            last_edited_by=page.last_edited_by.name or page.last_edited_by.id
        )

class TodoListResponse(BaseModel):
    """Response for todo list requests."""
    todos: List[TodoResponse]
    next_cursor: Optional[str] = None
    has_more: bool = False