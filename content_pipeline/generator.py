from typing import Dict, List, Optional
import json
import random
import time
from datetime import datetime, timedelta
import logging
from enum import Enum

class ContentType(Enum):
    BLOG_POST = "blog_post"
    SOCIAL_MEDIA = "social_media"
    NEWSLETTER = "newsletter"
    VIDEO_SCRIPT = "video_script"

class Platform(Enum):
    WORDPRESS = "wordpress"
    MEDIUM = "medium"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    YOUTUBE = "youtube"

class ContentGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rate_limit = {
            Platform.WORDPRESS: (10, 3600),  # 10 posts/hour
            Platform.MEDIUM: (5, 3600),
            Platform.LINKEDIN: (3, 3600),
            Platform.TWITTER: (15, 3600),
            Platform.YOUTUBE: (2, 86400)  # 2 videos/day
        }
        self.last_published = {p: datetime.min for p in Platform}

    def generate_content(self, content_type: ContentType, topic: str, keywords: List[str], 
                        word_count: Optional[int] = None) -> Dict:
        """Generate content based on type and parameters"""
        try:
            # TODO: Connect to actual content generation API/LLM
            template = self._get_template(content_type)
            content = template.format(
                topic=topic,
                keywords=", ".join(keywords),
                date=datetime.now().strftime("%B %d, %Y")
            )
            
            if word_count:
                content = self._adjust_length(content, word_count)
                
            return {
                "success": True,
                "content": content,
                "metadata": {
                    "type": content_type.value,
                    "generated_at": datetime.now().isoformat(),
                    "word_count": len(content.split())
                }
            }
        except Exception as e:
            self.logger.error(f"Content generation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def _get_template(self, content_type: ContentType) -> str:
        """Get template for content type"""
        templates = {
            ContentType.BLOG_POST: (
                "In-depth Analysis: {topic}\n\n"
                "Keywords: {keywords}\n\n"
                "Published on {date}\n\n"
                "This comprehensive article explores {topic} in detail..."
            ),
            ContentType.SOCIAL_MEDIA: (
                "Hot take on {topic}!\n\n"
                "#{topic.replace(' ', '')} #{keywords[0] if keywords else 'content'}\n\n"
                "What do you think about this?"
            ),
            ContentType.VIDEO_SCRIPT: (
                "Welcome to today's video about {topic}!\n\n"
                "Before we begin, don't forget to like and subscribe.\n\n"
                "Today we'll be discussing {topic} which is relevant because..."
            )
        }
        return templates.get(content_type, "Content about {topic} on {date}")

    def _adjust_length(self, content: str, target_words: int) -> str:
        """Adjust content to approximate word count"""
        words = content.split()
        if len(words) <= target_words:
            return content
            
        # Simple truncation for now - would use more sophisticated method in production
        return " ".join(words[:target_words]) + "..."

    def can_publish(self, platform: Platform) -> bool:
        """Check if we can publish to platform based on rate limits"""
        now = datetime.now()
        limit_count, limit_seconds = self.rate_limit[platform]
        last_pub = self.last_published[platform]
        
        if (now - last_pub) < timedelta(seconds=limit_seconds/limit_count):
            self.logger.warning(f"Rate limited on {platform.value}")
            return False
        return True

    def record_publish(self, platform: Platform):
        """Record successful publication"""
        self.last_published[platform] = datetime.now()
