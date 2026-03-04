"""
Plan Validation Layer — validates tool plan structure before MCP execution.
"""
from typing import List, Tuple


def validate_plan(plan) -> Tuple[bool, List[str]]:
    """
    Validate tool plan against structural rules.

    Rules:
      1. Plan must be a list
      2. Each step must be a dict
      3. Each step must have: step (int), name/tool (str), args/arguments (dict)
      4. depends_on must be int or null
      5. Step numbers must be sequential
      6. No duplicate step numbers

    Returns:
        (is_valid, errors)
    """
    errors = []

    if not isinstance(plan, list):
        return False, ["Plan harus berupa list"]

    if len(plan) == 0:
        return False, ["Plan kosong"]

    seen_steps = set()

    for i, step in enumerate(plan):
        if not isinstance(step, dict):
            errors.append(f"Step {i}: harus dict, got {type(step).__name__}")
            continue

        # Required: step number
        step_num = step.get("step")
        if step_num is None:
            errors.append(f"Step {i}: missing 'step'")
        elif not isinstance(step_num, int):
            errors.append(f"Step {i}: 'step' harus int, got {type(step_num).__name__}")
        else:
            if step_num in seen_steps:
                errors.append(f"Step {i}: duplicate step number {step_num}")
            seen_steps.add(step_num)

        # Required: name/tool
        name = step.get("name") or step.get("tool")
        if not name:
            errors.append(f"Step {i}: missing 'name' atau 'tool'")
        elif not isinstance(name, str):
            errors.append(f"Step {i}: 'name' harus str")

        # Args should be dict if present
        args = step.get("args") or step.get("arguments")
        if args is not None and not isinstance(args, dict):
            errors.append(f"Step {i}: 'args' harus dict, got {type(args).__name__}")

        # Optional: depends_on
        depends_on = step.get("depends_on")
        if depends_on is not None and not isinstance(depends_on, int):
            errors.append(f"Step {i}: 'depends_on' harus int atau null")

    # Check sequential numbering
    if seen_steps:
        sorted_steps = sorted(seen_steps)
        expected = list(range(sorted_steps[0], sorted_steps[0] + len(sorted_steps)))
        if sorted_steps != expected:
            errors.append(f"Step numbers harus sequential: got {sorted_steps}")

    return len(errors) == 0, errors
