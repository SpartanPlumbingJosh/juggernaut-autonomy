from typing import Dict, List, Optional
import json
from core.database import query_db

class SEOContentGenerator:
    """Automated SEO content generation and optimization."""
    
    def __init__(self):
        self.target_keywords = []
        
    async def generate_content(self, topic: str, keywords: List[str]) -> Dict[str, Any]:
        """Generate SEO-optimized content for a given topic."""
        try:
            # Analyze topic and keywords
            analysis = self._analyze_topic(topic, keywords)
            
            # Generate content outline
            outline = self._create_outline(analysis)
            
            # Generate full content
            content = self._write_content(outline)
            
            # Optimize for SEO
            optimized_content = self._optimize_content(content, keywords)
            
            # Save content
            insert_sql = f"""
                INSERT INTO seo_content (
                    id, topic, keywords, content,
                    created_at, updated_at
                ) VALUES (
                    gen_random_uuid(),
                    '{topic}',
                    '{json.dumps(keywords)}',
                    '{optimized_content}',
                    NOW(),
                    NOW()
                )
            """
            await query_db(insert_sql)
            
            return {"success": True, "content": optimized_content}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _analyze_topic(self, topic: str, keywords: List[str]) -> Dict[str, Any]:
        """Analyze topic and keywords for content generation."""
        return {
            "topic": topic,
            "keywords": keywords,
            "word_count": self._calculate_word_count(topic, keywords)
        }
        
    def _calculate_word_count(self, topic: str, keywords: List[str]) -> int:
        """Calculate target word count based on topic complexity."""
        base_count = 1000
        complexity = len(topic.split()) + len(keywords)
        return min(5000, base_count + complexity * 100)
        
    def _create_outline(self, analysis: Dict[str, Any]) -> List[str]:
        """Create content outline based on analysis."""
        outline = [
            f"Introduction to {analysis['topic']}",
            f"Why {analysis['topic']} matters",
            f"Key benefits of {analysis['topic']}"
        ]
        
        for keyword in analysis["keywords"]:
            outline.append(f"How {keyword} relates to {analysis['topic']}")
            
        outline.append(f"Conclusion: The future of {analysis['topic']}")
        return outline
        
    def _write_content(self, outline: List[str]) -> str:
        """Generate full content from outline."""
        content = ""
        for section in outline:
            content += f"<h2>{section}</h2>\n"
            content += f"<p>{' '.join([section] * 5)}</p>\n"
        return content
        
    def _optimize_content(self, content: str, keywords: List[str]) -> str:
        """Optimize content for SEO."""
        # Add meta tags
        meta = f"<meta name='keywords' content='{', '.join(keywords)}'>\n"
        
        # Add header tags
        optimized = meta + content
        
        # Add internal links
        optimized = optimized.replace(" ", " <a href='/related'>")
        
        return optimized
