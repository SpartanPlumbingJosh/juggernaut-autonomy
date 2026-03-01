from typing import Dict, List
import re

class QualityValidator:
    """Perform quality validation checks on deliverables."""
    
    def validate_report(self, report: str) -> Dict[str, Any]:
        """Validate analysis report quality."""
        errors = []
        
        # Check required sections
        required_sections = ["executive_summary", "analysis", "recommendations"]
        for section in required_sections:
            if f"<h2>{section.title().replace('_', ' ')}</h2>" not in report:
                errors.append(f"Missing section: {section}")
                
        # Check for placeholders
        if "{{" in report or "}}" in report:
            errors.append("Template placeholders found in final report")
            
        # Check formatting
        if len(report.splitlines()) < 50:
            errors.append("Report appears too short")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
    def validate_proposal(self, proposal: str) -> Dict[str, Any]:
        """Validate service proposal quality."""
        errors = []
        
        # Check required elements
        required_elements = ["scope", "timeline", "pricing"]
        for element in required_elements:
            if f"<h3>{element.title()}</h3>" not in proposal:
                errors.append(f"Missing element: {element}")
                
        # Check pricing format
        if "$0.00" in proposal:
            errors.append("Pricing appears incomplete")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
        
    def validate_summary(self, summary: str) -> Dict[str, Any]:
        """Validate executive summary quality."""
        errors = []
        
        # Check length
        if len(summary.splitlines()) < 10:
            errors.append("Summary appears too short")
            
        # Check metrics presence
        if "key_metrics" not in summary.lower():
            errors.append("Key metrics section missing")
            
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
