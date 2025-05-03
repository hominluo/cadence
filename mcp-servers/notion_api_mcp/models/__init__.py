"""
Notion API data models and validation.
"""
from enum import Enum
from typing import List

from .properties import (
    RichTextContent,
    RichTextObject,
    TitleProperty,
    RichTextProperty,
    DateValue,
    DateProperty,
    SelectOption,
    SelectProperty,
    MultiSelectProperty,
    NumberProperty,
    CheckboxProperty,
    StatusProperty,
    PropertyValue,
    PropertySchema,
    TodoProperties
)

from .responses import (
    User,
    Parent,
    DatabaseObject,
    PageObject,
    BlockObject,
    PaginatedList,
    DatabaseList,
    PageList,
    BlockList,
    ErrorResponse,
    SearchResponse,
    PropertyItemResponse,
    PropertyItemList,
    TodoResponse,
    TodoListResponse
)

class Priority(str, Enum):
    """Todo priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Status(str, Enum):
    """Todo status options."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class BlockType(str, Enum):
    """Supported block types."""
    PARAGRAPH = "paragraph"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    BULLETED_LIST = "bulleted_list_item"
    NUMBERED_LIST = "numbered_list_item"
    TO_DO = "to_do"
    TOGGLE = "toggle"
    CODE = "code"
    QUOTE = "quote"
    CALLOUT = "callout"
    DIVIDER = "divider"

class PropertyType(str, Enum):
    """Supported property types."""
    TITLE = "title"
    RICH_TEXT = "rich_text"
    NUMBER = "number"
    SELECT = "select"
    MULTI_SELECT = "multi_select"
    DATE = "date"
    CHECKBOX = "checkbox"
    STATUS = "status"

# Default database schema for todos
TODO_DATABASE_SCHEMA = {
    "Task": {
        "type": "title",
        "title": {}
    },
    "Description": {
        "type": "rich_text",
        "rich_text": {}
    },
    "Due Date": {
        "type": "date",
        "date": {}
    },
    "Priority": {
        "type": "select",
        "select": {
            "options": [
                {"name": Priority.HIGH, "color": "red"},
                {"name": Priority.MEDIUM, "color": "yellow"},
                {"name": Priority.LOW, "color": "blue"}
            ]
        }
    },
    "Tags": {
        "type": "multi_select",
        "multi_select": {
            "options": []  # Will be populated dynamically
        }
    },
    "Status": {
        "type": "status",
        "status": {
            "options": [
                {"name": Status.NOT_STARTED, "color": "gray"},
                {"name": Status.IN_PROGRESS, "color": "yellow"},
                {"name": Status.COMPLETED, "color": "green"}
            ]
        }
    }
}

__all__ = [
    # Enums
    'Priority',
    'Status',
    'BlockType',
    'PropertyType',
    # Property Models
    'RichTextContent',
    'RichTextObject',
    'TitleProperty',
    'RichTextProperty',
    'DateValue',
    'DateProperty',
    'SelectOption',
    'SelectProperty',
    'MultiSelectProperty',
    'NumberProperty',
    'CheckboxProperty',
    'StatusProperty',
    'PropertyValue',
    'PropertySchema',
    'TodoProperties',
    # Response Models
    'User',
    'Parent',
    'DatabaseObject',
    'PageObject',
    'BlockObject',
    'PaginatedList',
    'DatabaseList',
    'PageList',
    'BlockList',
    'ErrorResponse',
    'SearchResponse',
    'PropertyItemResponse',
    'PropertyItemList',
    'TodoResponse',
    'TodoListResponse',
    # Constants
    'TODO_DATABASE_SCHEMA'
]