# AI Spec Templates

This directory contains templates for creating AI-assisted coding specifications.

## Available Templates

- `standard_template.yml` - Comprehensive template with support for all patterns
- `refactor.yml` - Simplified template focused on refactoring tasks

## Field Descriptions

### Required Fields

- `plan_name`: A unique identifier for your plan
- `pattern`: The execution pattern to use (list, list-reflection, or list-director)
- `editable_context`: List of files the AI is allowed to modify
- `readonly_context`: List of files the AI can reference but not modify
- `high_level_objective`: Brief description of what the plan aims to accomplish
- `tasks`: A list of tasks for the AI to complete sequentially

### Optional Fields

- `architect`: Boolean flag to enable architect mode (default: false)
- `main_model`: The AI model to use for reasoning/drafting
- `editor_model`: The AI model to use for code implementation (when architect is true)
- `reasoning_effort`: Level of reasoning depth (low, medium, high)
- `implementation_details`: Detailed explanation of requirements and implementation guidelines

### Task Fields

Each task in the `tasks` list can have the following properties:

- `title`: Brief description of the task
- `prompt`: Detailed instructions for the AI
- `reflection_count`: Number of self-review cycles (for list-reflection pattern)
- `evaluator_count`: Number of evaluation attempts (for list-director pattern)
- `evaluator_command`: Command to run for validation (for list-director pattern)

## Pattern Types

1. **list**: Basic sequential execution of tasks
2. **list-reflection**: Tasks with additional self-review cycles
3. **list-director**: Tasks with command-based validation and retries

## Example Usage

```yaml
plan_name: "feature-x-implementation"
pattern: list-reflection
architect: true
main_model: "anthropic/claude-3-7-sonnet-20250219"
editor_model: "anthropic/claude-3-7-sonnet-20250219"

editable_context:
  - "./path/to/file.py"

readonly_context:
  - "./path/to/reference.py"

high_level_objective: "Implement Feature X"

implementation_details: |
  Feature X should do the following...

tasks:
  - title: "Implement core functionality"
    prompt: |
      Create the core functionality for Feature X...
    reflection_count: 2

  - title: "Add tests"
    prompt: |
      Create tests for Feature X...
    reflection_count: 1
```

## Best Practices

1. Be specific and detailed in your prompts
2. Break down complex tasks into smaller, focused tasks
3. Include relevant context files to help the AI understand your codebase
4. Use reflection for complex tasks that benefit from self-review
5. For critical functionality, consider using the list-director pattern with validation
