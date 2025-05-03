"""
Pydantic models for Notion property types and structures.
"""
from typing import List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

# Constants
MAX_TEXT_LENGTH = 2000
MAX_TITLE_LENGTH = 100

class RichTextContent(BaseModel):
    """Content for rich text objects."""
    content: str = Field(...)
    link: Optional[dict] = None

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate content is not empty and within length limits."""
        if not v or not v.strip():
            raise ValueError("Content cannot be empty")
        if len(v) > MAX_TEXT_LENGTH:
            raise ValueError(f"Content length exceeds maximum of {MAX_TEXT_LENGTH} characters")
        return v.strip()

class RichTextObject(BaseModel):
    """Rich text object with formatting."""
    type: str = Field("text", pattern="^text$")
    text: RichTextContent
    annotations: Optional[dict] = None
    plain_text: Optional[str] = None
    href: Optional[str] = None

    @field_validator('annotations')
    @classmethod
    def validate_annotations(cls, v: Optional[dict]) -> Optional[dict]:
        """Validate annotation format."""
        if v is not None:
            valid_keys = {'bold', 'italic', 'strikethrough', 'underline', 'code', 'color'}
            invalid_keys = set(v.keys()) - valid_keys
            if invalid_keys:
                raise ValueError(f"Invalid annotation keys: {invalid_keys}")
        return v

class TitleProperty(BaseModel):
    """Title property type."""
    type: str = "title"
    title: List[RichTextObject]

class RichTextProperty(BaseModel):
    """Rich text property type."""
    type: str = "rich_text"
    rich_text: List[RichTextObject]

class DateValue(BaseModel):
    """Date value with optional end date."""
    start: datetime
    end: Optional[datetime] = None
    time_zone: Optional[str] = None

class DateProperty(BaseModel):
    """Date property type."""
    type: str = "date"
    date: Optional[DateValue] = None

class SelectOption(BaseModel):
    """Option for select properties."""
    name: str
    color: Optional[str] = None

class SelectProperty(BaseModel):
    """Select property type."""
    type: str = "select"
    select: Optional[SelectOption] = None

class MultiSelectProperty(BaseModel):
    """Multi-select property type."""
    type: str = "multi_select"
    multi_select: List[SelectOption] = Field(default_factory=list)

class NumberProperty(BaseModel):
    """Number property type."""
    type: str = "number"
    number: Optional[float] = None
    format: Optional[str] = None

class CheckboxProperty(BaseModel):
    """Checkbox property type."""
    type: str = "checkbox"
    checkbox: Optional[bool] = None

class StatusProperty(BaseModel):
    """Status property type."""
    type: str = "status"
    status: Optional[SelectOption] = None

class PropertyValue(BaseModel):
    """Generic property value."""
    id: str
    type: str
    value: Union[
        TitleProperty,
        RichTextProperty,
        DateProperty,
        SelectProperty,
        MultiSelectProperty,
        NumberProperty,
        CheckboxProperty,
        StatusProperty
    ]

class PropertySchema(BaseModel):
    """Database property schema definition."""
    id: str
    name: str
    type: str
    config: Optional[dict] = None

class TodoProperties(BaseModel):
    """Properties for todo items."""
    task: str = Field(...)
    description: Optional[str] = Field(None, max_length=MAX_TEXT_LENGTH)
    due_date: Optional[datetime] = None
    priority: Optional[str] = Field(None, pattern="^(high|medium|low)$")
    tags: Optional[List[str]] = None
    status: Optional[str] = Field(None, pattern="^(not_started|in_progress|completed)$")

    @field_validator('task')
    @classmethod
    def validate_task(cls, v: str) -> str:
        """Validate task title."""
        if not v or not v.strip():
            raise ValueError("Task title cannot be empty")
        if len(v) > MAX_TITLE_LENGTH:
            raise ValueError(f"Task title exceeds maximum of {MAX_TITLE_LENGTH} characters")
        return v.strip()

    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description text."""
        if v is not None:
            if not v.strip():
                return None
            if len(v) > MAX_TEXT_LENGTH:
                raise ValueError(f"Description exceeds maximum of {MAX_TEXT_LENGTH} characters")
            return v.strip()
        return None

    def to_notion_properties(self) -> dict:
        """Convert to Notion API property format."""
        properties = {
            "Task": {
                "title": [{
                    "type": "text",
                    "text": {"content": self.task[:MAX_TITLE_LENGTH]}
                }]
            }
        }
        
        if self.description:
            properties["Description"] = {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": self.description[:MAX_TEXT_LENGTH]}
                }]
            }
            
        if self.due_date:
            properties["Due Date"] = {
                "date": {
                    "start": self.due_date.isoformat()
                }
            }
            
        if self.priority:
            properties["Priority"] = {
                "select": {"name": self.priority}
            }
            
        if self.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in self.tags]
            }
            
        if self.status:
            properties["Status"] = {
                "status": {"name": self.status}
            }
            
        return properties

    @classmethod
    def from_notion_properties(cls, properties: dict) -> "TodoProperties":
        """Create from Notion API property format."""
        return cls(
            task=properties["Task"]["title"][0]["text"]["content"]
            if properties.get("Task", {}).get("title")
            else "",
            description=properties["Description"]["rich_text"][0]["text"]["content"]
            if properties.get("Description", {}).get("rich_text")
            else None,
            due_date=datetime.fromisoformat(properties["Due Date"]["date"]["start"])
            if properties.get("Due Date", {}).get("date")
            else None,
            priority=properties["Priority"]["select"]["name"]
            if properties.get("Priority", {}).get("select")
            else None,
            tags=[tag["name"] for tag in properties["Tags"]["multi_select"]]
            if properties.get("Tags", {}).get("multi_select")
            else None,
            status=properties["Status"]["status"]["name"]
            if properties.get("Status", {}).get("status")
            else None
        )