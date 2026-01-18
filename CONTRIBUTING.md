# Contributing to JUGGERNAUT

## Development Workflow

1. Create a feature branch from `main`
2. Make your changes
3. Run tests locally: `pytest tests/ -v`
4. Run linter: `flake8 .`
5. Submit a pull request

## Code Standards

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Max line length: 127 characters

## Commit Messages

Format: `<type>: <description>`

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Adding tests
- `chore`: Maintenance

Examples:
```
feat: Add revenue tracking function
fix: Handle null values in opportunity scoring
docs: Update database schema documentation
```

## Adding New Functions

### Database Functions (core/database.py)

1. Add function with type hints
2. Include docstring with Args/Returns
3. Log actions via `log_execution()`
4. Handle exceptions gracefully

Example:
```python
def my_function(
    required_param: str,
    optional_param: int = 0
) -> Optional[str]:
    """
    Brief description.
    
    Args:
        required_param: What this is
        optional_param: What this is (default: 0)
    
    Returns:
        Description of return value
    """
    try:
        # Implementation
        log_execution(
            worker_id="SYSTEM",
            action="my_function",
            message="Did the thing"
        )
        return result
    except Exception as e:
        print(f"Error: {e}")
        return None
```

## Testing

- Test files go in `tests/`
- Name files `test_<module>.py`
- Name functions `test_<behavior>()`

## Questions?

Open an issue or reach out to the team.
