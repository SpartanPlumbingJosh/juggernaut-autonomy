"""
SEO Content Pipeline - Automates content generation and optimization.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional

from core.database import query_db
from core.ai import generate_seo_content

async def generate_blog_post(topic: str, keywords: List[str]) -> Dict[str, Any]:
    """Generate SEO-optimized blog post."""
    try:
        content = await generate_seo_content(
            prompt=f"Write a comprehensive blog post about {topic}",
            keywords=keywords,
            tone="professional",
            word_count=1500
        )
        
        # Save to database
        sql = """
        INSERT INTO seo_content (title, content, keywords, status, created_at)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """
        result = await query_db(sql, [
            content["title"],
            content["content"],
            json.dumps(keywords),
            "draft",
            datetime.utcnow()
        ])
        
        return {
            "id": result["rows"][0]["id"],
            "title": content["title"],
            "content": content["content"],
            "keywords": keywords
        }
        
    except Exception as e:
        raise Exception(f"Failed to generate blog post: {str(e)}")


async def optimize_existing_content(content_id: int) -> Dict[str, Any]:
    """Optimize existing content for SEO."""
    try:
        # Get content
        sql = "SELECT * FROM seo_content WHERE id = %s"
        result = await query_db(sql, [content_id])
        content = result["rows"][0]
        
        # Generate optimized version
        optimized = await generate_seo_content(
            prompt=f"Optimize this content for SEO: {content['content']}",
            keywords=json.loads(content["keywords"]),
            tone="professional",
            word_count=len(content["content"].split())
        )
        
        # Update database
        update_sql = """
        UPDATE seo_content 
        SET content = %s, title = %s, status = 'optimized', updated_at = %s
        WHERE id = %s
        """
        await query_db(update_sql, [
            optimized["content"],
            optimized["title"],
            datetime.utcnow(),
            content_id
        ])
        
        return {
            "id": content_id,
            "title": optimized["title"],
            "content": optimized["content"]
        }
        
    except Exception as e:
        raise Exception(f"Failed to optimize content: {str(e)}")


async def schedule_content_publishing(content_id: int, publish_at: datetime) -> Dict[str, Any]:
    """Schedule content for publishing."""
    try:
        sql = """
        UPDATE seo_content 
        SET status = 'scheduled', publish_at = %s
        WHERE id = %s
        """
        await query_db(sql, [publish_at, content_id])
        
        return {"id": content_id, "status": "scheduled", "publish_at": publish_at}
        
    except Exception as e:
        raise Exception(f"Failed to schedule content: {str(e)}")


__all__ = ["generate_blog_post", "optimize_existing_content", "schedule_content_publishing"]
