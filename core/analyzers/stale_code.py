"""
Stale Code Detector

Detects unused imports, functions, and dead code in Python files.

Part of Milestone 4: GitHub Code Crawler
"""

import ast
import logging
from typing import List, Dict, Any, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class StaleCodeDetector:
    """Detects stale and unused code."""
    
    def __init__(self):
        self.findings = []
    
    def analyze_file(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """
        Analyze a Python file for stale code.
        
        Args:
            file_path: Path to file
            content: File content
            
        Returns:
            List of findings
        """
        self.findings = []
        
        try:
            tree = ast.parse(content, filename=file_path)
            
            # Detect unused imports
            self._detect_unused_imports(tree, file_path)
            
            # Detect unused functions
            self._detect_unused_functions(tree, file_path)
            
            # Detect commented code
            self._detect_commented_code(content, file_path)
            
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
        except Exception as e:
            logger.exception(f"Error analyzing {file_path}: {e}")
        
        return self.findings
    
    def _detect_unused_imports(self, tree: ast.AST, file_path: str):
        """Detect unused imports."""
        # Collect all imports
        imports = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = {
                        'line': node.lineno,
                        'module': alias.name,
                        'used': False
                    }
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname if alias.asname else alias.name
                    imports[name] = {
                        'line': node.lineno,
                        'module': f"{node.module}.{alias.name}" if node.module else alias.name,
                        'used': False
                    }
        
        # Check usage
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id in imports:
                    imports[node.id]['used'] = True
            elif isinstance(node, ast.Attribute):
                # Handle module.function usage
                if isinstance(node.value, ast.Name):
                    if node.value.id in imports:
                        imports[node.value.id]['used'] = True
        
        # Report unused imports
        for name, info in imports.items():
            if not info['used']:
                self.findings.append({
                    'type': 'unused_import',
                    'severity': 'low',
                    'file_path': file_path,
                    'line_number': info['line'],
                    'description': f"Unused import: {info['module']}",
                    'suggestion': f"Remove unused import '{name}'",
                    'auto_fixable': True
                })
    
    def _detect_unused_functions(self, tree: ast.AST, file_path: str):
        """Detect unused functions."""
        # Collect all function definitions
        functions = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Skip private functions (might be used externally)
                if not node.name.startswith('_'):
                    functions[node.name] = {
                        'line': node.lineno,
                        'used': False
                    }
        
        # Check usage
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id in functions:
                    functions[node.id]['used'] = True
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in functions:
                        functions[node.func.id]['used'] = True
        
        # Report unused functions
        for name, info in functions.items():
            if not info['used']:
                self.findings.append({
                    'type': 'unused_function',
                    'severity': 'medium',
                    'file_path': file_path,
                    'line_number': info['line'],
                    'description': f"Unused function: {name}",
                    'suggestion': f"Consider removing unused function '{name}' or mark as private",
                    'auto_fixable': False  # Might be public API
                })
    
    def _detect_commented_code(self, content: str, file_path: str):
        """Detect commented-out code blocks."""
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Look for commented code patterns
            if stripped.startswith('#'):
                # Remove the comment marker
                code_like = stripped[1:].strip()
                
                # Check if it looks like code
                if any([
                    code_like.startswith('def '),
                    code_like.startswith('class '),
                    code_like.startswith('import '),
                    code_like.startswith('from '),
                    '=' in code_like and not code_like.startswith('TODO'),
                    code_like.startswith('return '),
                    code_like.startswith('if '),
                    code_like.startswith('for '),
                    code_like.startswith('while '),
                ]):
                    self.findings.append({
                        'type': 'commented_code',
                        'severity': 'low',
                        'file_path': file_path,
                        'line_number': i,
                        'description': f"Commented-out code: {code_like[:50]}",
                        'suggestion': "Remove commented code or uncomment if needed",
                        'auto_fixable': False
                    })
    
    def analyze_repository(
        self,
        file_contents: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple files.
        
        Args:
            file_contents: Dict mapping file paths to content
            
        Returns:
            List of all findings
        """
        all_findings = []
        
        for file_path, content in file_contents.items():
            if file_path.endswith('.py'):
                findings = self.analyze_file(file_path, content)
                all_findings.extend(findings)
        
        return all_findings


# Singleton instance
_stale_detector = None


def get_stale_detector() -> StaleCodeDetector:
    """Get or create stale code detector singleton."""
    global _stale_detector
    if _stale_detector is None:
        _stale_detector = StaleCodeDetector()
    return _stale_detector


__all__ = ["StaleCodeDetector", "get_stale_detector"]
