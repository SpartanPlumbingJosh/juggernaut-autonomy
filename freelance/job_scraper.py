import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
from typing import List, Dict, Optional
import logging

class JobScraper:
    """Scrape freelance job boards for relevant opportunities."""
    
    def __init__(self, platforms: List[str], keywords: List[str], rate_limit: int = 1):
        self.platforms = platforms
        self.keywords = keywords
        self.rate_limit = rate_limit
        self.last_request_time = 0
        self.logger = logging.getLogger(__name__)
        
    def _rate_limit_check(self):
        """Enforce rate limiting to prevent platform bans."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self.last_request_time = time.time()
        
    def scrape_upwork(self) -> List[Dict[str, Any]]:
        """Scrape Upwork job feed."""
        self._rate_limit_check()
        try:
            url = "https://www.upwork.com/nx/jobs/search/"
            params = {
                "q": " ".join(self.keywords),
                "sort": "recency"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            jobs = []
            
            for job in soup.select('section.job-tile'):
                title = job.select_one('h2.job-tile-title')
                if not title:
                    continue
                    
                job_data = {
                    "platform": "Upwork",
                    "title": title.text.strip(),
                    "url": f"https://www.upwork.com{job.select_one('a')['href']}",
                    "description": job.select_one('p.job-description').text.strip(),
                    "posted": job.select_one('span.posted-on').text.strip(),
                    "budget": job.select_one('span.amount').text.strip() if job.select_one('span.amount') else None,
                    "skills": [skill.text.strip() for skill in job.select('span.skills-element')],
                    "scraped_at": datetime.utcnow().isoformat()
                }
                jobs.append(job_data)
                
            return jobs
            
        except Exception as e:
            self.logger.error(f"Failed to scrape Upwork: {str(e)}")
            return []
            
    def scrape_all(self) -> List[Dict[str, Any]]:
        """Scrape all configured platforms."""
        jobs = []
        for platform in self.platforms:
            if platform == "upwork":
                jobs.extend(self.scrape_upwork())
        return jobs
