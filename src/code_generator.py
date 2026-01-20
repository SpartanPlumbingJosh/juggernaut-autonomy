"""
Code Generator Module for JUGGERNAUT

AI-powered code generation using OpenRouter smart routing.
Integrates with GitHub automation for autonomous development workflow.
"""

import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# Configure module logger
logger = logging.getLogger(__name__)

# OpenRouter configuration
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openrouter/auto"  # Smart router - auto-selects best model
MAX_TOKENS_DEFAULT = 4096
TEMPERATURE_DEFAULT = 0.7


class CodeGenerationError(Exception):
    """Exception for code generation failures."""
    pass


@dataclass
class GeneratedCode:
    """Container for generated code output."""
    content: str
    language: str
    filename: str
    model_used: str
    tokens_used: int
    reasoning: Optional[str] = None


class CodeGenerator:
    """
    AI-powered code generator using OpenRouter smart routing.
    
    Uses OpenRouter's auto model selection to choose the best model
    for each code generation task, optimizing for quality and cost.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS_DEFAULT,
        temperature: float = TEMPERATURE_DEFAULT
    ):
        """
        Initialize code generator.
        
        Args:
            api_key: OpenRouter API key. Defaults to OPENROUTER_API_KEY env var.
            model: Model to use. Defaults to "openrouter/auto" (smart routing).
            max_tokens: Maximum tokens for response.
            temperature: Sampling temperature (0-1).
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        if not self.api_key:
            logger.warning("No OPENROUTER_API_KEY found - code generation will fail")
    
    def _make_request(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Make a request to OpenRouter API.
        
        Args:
            messages: List of message dicts with role and content.
            
        Returns:
            API response as dict.
            
        Raises:
            CodeGenerationError: If API call fails.
        """
        if not self.api_key:
            raise CodeGenerationError("OpenRouter API key not configured")
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://juggernaut-autonomy.railway.app",
            "X-Title": "JUGGERNAUT Code Generator"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        try:
            req = urllib.request.Request(
                OPENROUTER_ENDPOINT,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
                
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else str(e)
            raise CodeGenerationError(f"OpenRouter API error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise CodeGenerationError(f"Connection error: {e}")
        except json.JSONDecodeError as e:
            raise CodeGenerationError(f"Invalid JSON response: {e}")
    
    def generate_module(
        self,
        task_description: str,
        module_name: str,
        requirements: Optional[List[str]] = None,
        existing_code: Optional[str] = None
    ) -> GeneratedCode:
        """
        Generate a Python module based on task description.
        
        Args:
            task_description: What the module should do.
            module_name: Name for the module file.
            requirements: List of specific requirements.
            existing_code: Existing code to modify/extend.
            
        Returns:
            GeneratedCode with the generated module.
        """
        system_prompt = """You are an expert Python developer for the JUGGERNAUT autonomous system.

Generate production-quality Python code following these standards:
- Type hints on ALL function parameters and return types
- Docstrings on ALL classes and functions (Google style)
- Specific exception handling (no bare except)
- Use logging instead of print statements
- Constants for magic numbers
- Parameterized SQL queries (if applicable)
- Imports grouped: stdlib, third-party, local

The code must be complete, runnable, and follow best practices."""

        user_prompt = f"""Generate a Python module for: {task_description}

Module name: {module_name}
"""
        
        if requirements:
            user_prompt += f"\nRequirements:\n" + "\n".join(f"- {r}" for r in requirements)
        
        if existing_code:
            user_prompt += f"\n\nExisting code to extend/modify:\n```python\n{existing_code}\n```"
        
        user_prompt += "\n\nReturn ONLY the Python code, no markdown formatting."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages)
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = response.get("model", self.model)
        tokens = response.get("usage", {}).get("total_tokens", 0)
        
        # Clean up code if wrapped in markdown
        if content.startswith("```python"):
            content = content[9:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        logger.info(f"Generated {module_name} using {model_used} ({tokens} tokens)")
        
        return GeneratedCode(
            content=content,
            language="python",
            filename=f"{module_name}.py" if not module_name.endswith(".py") else module_name,
            model_used=model_used,
            tokens_used=tokens
        )
    
    def generate_fix(
        self,
        code: str,
        error_message: str,
        context: Optional[str] = None
    ) -> GeneratedCode:
        """
        Generate a fix for broken code.
        
        Args:
            code: The code with the error.
            error_message: The error message or description.
            context: Additional context about the issue.
            
        Returns:
            GeneratedCode with the fixed code.
        """
        system_prompt = """You are an expert Python debugger for the JUGGERNAUT autonomous system.

Fix the provided code while:
- Maintaining all existing functionality
- Following code quality standards (type hints, docstrings, etc.)
- Adding appropriate error handling
- Explaining the fix in a brief comment"""

        user_prompt = f"""Fix this code:

```python
{code}
```

Error: {error_message}
"""
        
        if context:
            user_prompt += f"\nContext: {context}"
        
        user_prompt += "\n\nReturn ONLY the fixed Python code, no markdown."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages)
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = response.get("model", self.model)
        tokens = response.get("usage", {}).get("total_tokens", 0)
        
        # Clean up
        if content.startswith("```python"):
            content = content[9:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        logger.info(f"Generated fix using {model_used} ({tokens} tokens)")
        
        return GeneratedCode(
            content=content,
            language="python",
            filename="fix.py",
            model_used=model_used,
            tokens_used=tokens
        )
    
    def generate_tests(
        self,
        module_code: str,
        module_name: str
    ) -> GeneratedCode:
        """
        Generate unit tests for a module.
        
        Args:
            module_code: The module code to test.
            module_name: Name of the module being tested.
            
        Returns:
            GeneratedCode with test code.
        """
        system_prompt = """You are an expert Python test engineer.

Generate comprehensive pytest unit tests that:
- Cover all public functions and classes
- Include edge cases and error conditions
- Use appropriate fixtures and mocking
- Follow pytest best practices
- Have descriptive test names"""

        user_prompt = f"""Generate unit tests for this module ({module_name}):

```python
{module_code}
```

Return ONLY the test code, no markdown formatting."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages)
        
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = response.get("model", self.model)
        tokens = response.get("usage", {}).get("total_tokens", 0)
        
        # Clean up
        if content.startswith("```python"):
            content = content[9:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        test_filename = f"test_{module_name}" if not module_name.startswith("test_") else module_name
        if not test_filename.endswith(".py"):
            test_filename += ".py"
        
        logger.info(f"Generated tests for {module_name} using {model_used} ({tokens} tokens)")
        
        return GeneratedCode(
            content=content,
            language="python",
            filename=test_filename,
            model_used=model_used,
            tokens_used=tokens
        )
    
    def review_code(self, code: str) -> Dict[str, Any]:
        """
        Review code and suggest improvements.
        
        Args:
            code: Code to review.
            
        Returns:
            Dict with issues, suggestions, and quality score.
        """
        system_prompt = """You are a senior code reviewer. Analyze the code and return a JSON object with:
{
    "quality_score": 1-10,
    "issues": ["list of issues"],
    "suggestions": ["list of improvements"],
    "security_concerns": ["any security issues"],
    "summary": "brief overall assessment"
}"""

        user_prompt = f"""Review this Python code:

```python
{code}
```

Return ONLY valid JSON, no markdown."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        response = self._make_request(messages)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        
        # Clean up JSON
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {
                "quality_score": 0,
                "issues": ["Failed to parse review"],
                "suggestions": [],
                "security_concerns": [],
                "summary": content[:200]
            }


def get_generator() -> CodeGenerator:
    """Get a configured code generator instance."""
    return CodeGenerator()


def generate_and_commit(
    task_description: str,
    module_name: str,
    branch_name: str,
    requirements: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Generate code and commit it to a branch.
    
    Combines code generation with GitHub automation for
    end-to-end autonomous development.
    
    Args:
        task_description: What to build.
        module_name: Name for the module.
        branch_name: Git branch to commit to.
        requirements: Specific requirements.
        
    Returns:
        Dict with generated code info and commit status.
    """
    from src.github_automation import GitHubClient
    
    # Generate the code
    generator = get_generator()
    code = generator.generate_module(task_description, module_name, requirements)
    
    # Generate tests
    tests = generator.generate_tests(code.content, module_name)
    
    # Commit to GitHub
    github = GitHubClient()
    github.create_branch(branch_name)
    
    # Commit module
    module_path = f"src/{code.filename}"
    github.commit_file(
        branch=branch_name,
        path=module_path,
        content=code.content,
        message=f"feat: add {module_name} module"
    )
    
    # Commit tests
    test_path = f"tests/{tests.filename}"
    github.commit_file(
        branch=branch_name,
        path=test_path,
        content=tests.content,
        message=f"test: add tests for {module_name}"
    )
    
    return {
        "module": {
            "path": module_path,
            "model": code.model_used,
            "tokens": code.tokens_used
        },
        "tests": {
            "path": test_path,
            "model": tests.model_used,
            "tokens": tests.tokens_used
        },
        "branch": branch_name,
        "status": "committed"
    }


__all__ = [
    "CodeGenerator",
    "CodeGenerationError",
    "GeneratedCode",
    "get_generator",
    "generate_and_commit",
]
