"""
Text and content formatting utilities.
"""
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import re
from ..models import (
    BlockType,
    RichTextContent,
    RichTextObject
)

def create_rich_text(
    content: str,
    link: Optional[str] = None,
    annotations: Optional[Dict[str, bool]] = None
) -> List[Dict[str, Any]]:
    """
    Create rich text array for Notion API.
    
    Args:
        content: Text content
        link: Optional URL
        annotations: Text formatting options
        
    Returns:
        List of rich text objects
        
    Raises:
        ValueError: If content is empty/None or annotations are invalid
    """
    if not content:
        raise ValueError("Content cannot be empty")
        
    # Validate annotations
    valid_annotations = {"bold", "italic", "strikethrough", "underline", "code", "color"}
    if annotations:
        invalid_annotations = set(annotations.keys()) - valid_annotations
        if invalid_annotations:
            raise ValueError(f"Invalid annotations: {invalid_annotations}")
            
        # Validate color if present
        if "color" in annotations and not isinstance(annotations["color"], str):
            raise ValueError("Color annotation must be a string")
            
    # Validate content using RichTextContent model
    validated_content = RichTextContent(content=content, link={"url": link} if link else None)
    
    text = {
        "content": validated_content.content,
        **({"link": validated_content.link} if validated_content.link else {})
    }
        
    rich_text = {
        "type": "text",
        "text": text
    }
    
    if annotations:
        rich_text["annotations"] = annotations
        
    return [rich_text]

def create_block(
    content: str,
    block_type: Union[BlockType, str],
    annotations: Optional[Dict[str, bool]] = None,
    extra_props: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a block object for Notion API.
    
    Args:
        content: Block content
        block_type: Type of block (BlockType enum or string)
        annotations: Text formatting options
        extra_props: Additional block properties
        
    Returns:
        Block object
        
    Raises:
        ValueError: If content is empty or block type is invalid
    """
    if not content and block_type != BlockType.CODE:
        raise ValueError("Content cannot be empty")
        
    # Convert string block type to enum if needed
    if isinstance(block_type, str):
        try:
            block_type = BlockType(block_type)
        except ValueError:
            raise ValueError(f"Invalid block type: {block_type}")
            
    # Validate annotations
    if annotations:
        valid_annotations = {"bold", "italic", "strikethrough", "underline", "code", "color"}
        invalid_annotations = set(annotations.keys()) - valid_annotations
        if invalid_annotations:
            raise ValueError(f"Invalid annotations: {invalid_annotations}")
    
    block = {
        "type": block_type.value,
        block_type.value: {}
    }

    # Handle code blocks differently
    if block_type == BlockType.CODE:
        # For code blocks, rich_text contains the language
        if extra_props and "language" in extra_props:
            block[block_type.value]["rich_text"] = create_rich_text(extra_props["language"])
            block[block_type.value]["language"] = extra_props["language"]
        # Store actual code content separately
        if content:
            block[block_type.value]["content"] = content
    else:
        block[block_type.value]["rich_text"] = create_rich_text(content, annotations=annotations)
        if extra_props:
            block[block_type.value].update(extra_props)
        
    return block

def format_date(date: datetime) -> str:
    """
    Format datetime for Notion API.
    
    Args:
        date: Datetime to format
        
    Returns:
        ISO formatted date string
    """
    return date.isoformat()

def parse_markdown_to_blocks(markdown: str) -> List[Dict[str, Any]]:
    """
    Convert markdown text to Notion blocks.
    
    Args:
        markdown: Markdown formatted text
        
    Returns:
        List of Notion blocks
        
    Raises:
        ValueError: If markdown is invalid or contains unsupported formatting
    """
    blocks = []
    if not markdown:
        return blocks
    lines = markdown.split('\n')
    in_code_block = False
    code_content = []
    code_language = None
    
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        
        if not line and not in_code_block:
            i += 1
            continue
            
        # Code blocks
        if line.startswith('```'):
            if not in_code_block:
                in_code_block = True
                code_content = []
                code_language = line[3:] if len(line) > 3 else ""
            else:
                # Create code block with language in rich_text and code in content
                extra_props = {}
                if code_language:
                    extra_props["language"] = code_language
                blocks.append(create_block(
                    '\n'.join(code_content) if code_content else "",
                    BlockType.CODE,
                    extra_props=extra_props
                ))
                in_code_block = False
                code_language = None
            i += 1
            continue
            
        if in_code_block:
            code_content.append(line)
            i += 1
            continue
            
        try:
            # Headers
            if line.startswith('# '):
                blocks.append(create_block(
                    line[2:].strip(),
                    BlockType.HEADING_1
                ))
            elif line.startswith('## '):
                blocks.append(create_block(
                    line[3:].strip(),
                    BlockType.HEADING_2
                ))
            elif line.startswith('### '):
                blocks.append(create_block(
                    line[4:].strip(),
                    BlockType.HEADING_3
                ))
                
            # Lists
            elif line.startswith('- '):
                blocks.append(create_block(
                    line[2:].strip(),
                    BlockType.BULLETED_LIST
                ))
            elif re.match(r'^\d+\. ', line):
                content = re.sub(r'^\d+\. ', '', line).strip()
                blocks.append(create_block(
                    content,
                    BlockType.NUMBERED_LIST
                ))
                
            # Todo
            elif line.startswith('[ ] '):
                blocks.append(create_block(
                    line[4:].strip(),
                    BlockType.TO_DO,
                    extra_props={"checked": False}
                ))
            elif line.startswith('[x] '):
                blocks.append(create_block(
                    line[4:].strip(),
                    BlockType.TO_DO,
                    extra_props={"checked": True}
                ))
                
            # Quote
            elif line.startswith('> '):
                blocks.append(create_block(
                    line[2:].strip(),
                    BlockType.QUOTE
                ))
                
            # Default to paragraph
            else:
                blocks.append(create_block(
                    line.strip(),
                    BlockType.PARAGRAPH
                ))
                
        except ValueError as e:
            raise ValueError(f"Error parsing line {i + 1}: {str(e)}")
        
        i += 1
        
    if in_code_block:
        raise ValueError("Unclosed code block at end of markdown")
    
    return blocks

def blocks_to_markdown(blocks: List[Dict[str, Any]]) -> str:
    """
    Convert Notion blocks to markdown text.
    
    Args:
        blocks: List of Notion blocks
        
    Returns:
        Markdown formatted text
    """
    markdown = []
    i = 0
    numbered_list_counter = 0
    
    while i < len(blocks):
        block = blocks[i]
        block_type = block["type"]
        
        # Handle code blocks specially first
        if block_type == BlockType.CODE.value:
            language = block[block_type].get("language", "")
            code_content = block[block_type].get("content", "")
            markdown.append(f"```{language}")
            if code_content:
                markdown.append(code_content)
            else:
                # Fallback to rich_text content if no separate content field
                markdown.append(block[block_type]["rich_text"][0]["text"]["content"])
            markdown.append("```")
            # Add blank line after code block unless it's the last block
            if i + 1 < len(blocks):
                markdown.append("")
            i += 1
            continue

        # For all other blocks, get content from rich_text
        content = block[block_type]["rich_text"][0]["text"]["content"]
        
        if block_type == BlockType.HEADING_1.value:
            markdown.append(f"# {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.HEADING_2.value:
            markdown.append(f"## {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.HEADING_3.value:
            markdown.append(f"### {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.BULLETED_LIST.value:
            markdown.append(f"- {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.NUMBERED_LIST.value:
            numbered_list_counter += 1
            markdown.append(f"{numbered_list_counter}. {content}")
        elif block_type == BlockType.TO_DO.value:
            checked = block[block_type].get("checked", False)
            markdown.append(f"[{'x' if checked else ' '}] {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.QUOTE.value:
            markdown.append(f"> {content}")
            numbered_list_counter = 0
        elif block_type == BlockType.PARAGRAPH.value:
            markdown.append(content)
            numbered_list_counter = 0
            
        # Add blank line between blocks
        if i + 1 < len(blocks):
            next_block_type = blocks[i + 1]["type"]
            # Don't add blank line between consecutive list items of the same type
            if not (block_type in {BlockType.NUMBERED_LIST.value, BlockType.BULLETED_LIST.value} and
                   block_type == next_block_type):
                markdown.append("")
        else:
            # Add blank line after last block unless it's the only block
            if len(blocks) > 1:
                markdown.append("")
            
        i += 1
    
    return "\n".join(markdown).strip()

def format_rich_text_content(rich_text: List[RichTextObject]) -> str:
    """
    Extract plain text content from rich text objects.
    
    Args:
        rich_text: List of rich text objects
        
    Returns:
        Plain text content
    """
    return " ".join(
        obj.text.content
        for obj in rich_text
        if obj.text and obj.text.content
    )