from typing import Dict, List, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class ContentGenerator:
    """Automated content generation pipeline"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.templates = {
            'email': "Subject: {title}\n\n{content}",
            'landing_page': "<h1>{title}</h1>\n<p>{content}</p>",
            'social_media': "{title}: {content}"
        }
        
    def generate_content(self, idea: Dict[str, Any], format: str = 'email') -> Optional[str]:
        """Generate content based on idea"""
        try:
            template = self.templates.get(format)
            if not template:
                logger.error(f"Invalid content format: {format}")
                return None
                
            return template.format(
                title=idea.get('title', ''),
                content=idea.get('description', '')
            )
        except Exception as e:
            logger.error(f"Content generation failed: {str(e)}")
            return None
            
    def batch_generate(self, ideas: List[Dict[str, Any]], format: str = 'email') -> List[str]:
        """Generate multiple content pieces"""
        return [self.generate_content(idea, format) for idea in ideas]
