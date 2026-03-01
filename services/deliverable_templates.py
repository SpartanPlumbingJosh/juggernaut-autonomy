from datetime import datetime
from typing import Dict, List
import jinja2

class DeliverableTemplates:
    """Generate standardized deliverables using templates."""
    
    def __init__(self):
        self.template_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader("templates"),
            autoescape=True
        )
        
    def generate_report(self, client_data: Dict[str, Any], analysis_results: Dict[str, Any]) -> str:
        """Generate analysis report."""
        template = self.template_env.get_template("analysis_report.html")
        return template.render(
            client=client_data,
            analysis=analysis_results,
            generated_at=datetime.utcnow()
        )
        
    def generate_proposal(self, client_data: Dict[str, Any], pricing: Dict[str, Any]) -> str:
        """Generate service proposal."""
        template = self.template_env.get_template("service_proposal.html")
        return template.render(
            client=client_data,
            pricing=pricing,
            valid_until=(datetime.utcnow() + timedelta(days=30)).date()
        )
        
    def generate_summary(self, client_data: Dict[str, Any], key_metrics: Dict[str, Any]) -> str:
        """Generate executive summary."""
        template = self.template_env.get_template("executive_summary.html")
        return template.render(
            client=client_data,
            metrics=key_metrics,
            generated_at=datetime.utcnow()
        )
