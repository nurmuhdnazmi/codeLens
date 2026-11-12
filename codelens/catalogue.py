from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Verification:
    question: str
    candidate_source: str
    choices: tuple[str, ...]
    answer: str
    rationale: str


@dataclass(frozen=True, slots=True)
class Example:
    id: str
    title: str
    task: str
    source: str
    mock_explanation: str
    verification: Verification
    prediction_prompt: str = "Predict all four printed lines"
    expected_exception_type: str | None = None


_LIST_APPEND = Example(
    id="list_append",
    title="List append",
    task=(
        "Append an integer to a list and return it. Every call without a "
        "supplied list must start empty. When a list is supplied, update "
        "that same list."
    ),
    source=(
        "def append_item(item, values=[]):\n"
        "    values.append(item)\n"
        "    return values\n"
        "\n"
        "print(append_item(1))\n"
        "print(append_item(2))\n"
        "print(append_item(3, []))\n"
        "print(append_item(4))\n"
    ),
    mock_explanation=(
        "The default list is created once when the function is defined. Calls that "
        "omit the list reuse that same object. The task requires each such call to "
        "start empty, but the second printed line includes the earlier item.\n\n"
        "The third call supplies a separate empty list. It updates that supplied "
        "list without replacing or resetting the default list. The fourth call "
        "omits the list again and continues using the original default."
    ),
    verification=Verification(
        question="Does this replacement meet the original task’s requirements?",
        candidate_source=(
            "def append_item(item, values=None):\n"
            "    if values is None:\n"
            "        values = []\n"
            "    values.append(item)\n"
            "    return values\n"
        ),
        choices=("Meets the task", "Does not meet the task", "Not sure"),
        answer="Meets the task",
        rationale=(
            "Omitting the list creates a fresh list inside each call. An explicitly "
            "supplied list, including an empty list, is updated in place because "
            "the replacement only creates a list when values is None."
        ),
    ),
)


_AVERAGE = Example(
    id="average",
    title="Average",
    task=(
        "Return the mean of a list of finite numbers, or None when the list is empty. "
        "Assume ordinary Python arithmetic and values whose sum does not overflow."
    ),
    source=(
        "def average(values):\n"
        "    return sum(values) / len(values)\n"
        "\n"
        "print(average([2, 4, 6]))\n"
        "print(average([]))\n"
    ),
    prediction_prompt="Predict the output or exception for both calls",
    expected_exception_type="builtins.ZeroDivisionError",
    mock_explanation=(
        "The first call prints the mean of the non-empty list. The empty-list call "
        "then divides zero by zero because both sum(values) and len(values) are zero. "
        "Python raises ZeroDivisionError, so that call does not print a returned value.\n\n"
        "The task requires None for an empty list. The earlier stdout and actual "
        "traceback are evidence of this specification mismatch; the exception is "
        "not a runner failure."
    ),
    verification=Verification(
        question="Does this replacement meet the original task’s requirements?",
        candidate_source=(
            "def average(values):\n"
            "    if not values:\n"
            "        return 0\n"
            "    return sum(values) / len(values)\n"
        ),
        choices=("Meets the task", "Does not meet the task", "Not sure"),
        answer="Does not meet the task",
        rationale=(
            "The replacement avoids division by zero, but returns 0 for an empty "
            "list. The specification requires None, so avoiding the exception alone "
            "does not satisfy the task."
        ),
    ),
)


_REMOVE_DUPLICATES = Example(
    id="remove_duplicates",
    title="Remove duplicates",
    task=(
        "Remove duplicate integers, preserve first-seen order, return a new list "
        "and leave the input unchanged."
    ),
    source=(
        "def remove_duplicates(values):\n"
        "    return list(set(values))\n"
        "\n"
        "values = [3, 1, 3, 2]\n"
        "print(remove_duplicates(values))\n"
        "print(values)\n"
        "print(remove_duplicates([]))\n"
        "print(remove_duplicates([5, 5, 5]))\n"
    ),
    mock_explanation=(
        "Converting to a set removes duplicates but does not guarantee first-seen "
        "order. The task requires [3, 1, 2] for [3, 1, 3, 2]. The actual stdout "
        "shows the iteration order observed on this run; a coincidentally matching "
        "output would not establish an order-preservation guarantee.\n\n"
        "The suggestion returns a new list and leaves the input unchanged. Those "
        "properties do not resolve the missing order guarantee. Empty input and "
        "repeated identical integers also provide limited coverage of ordering."
    ),
    verification=Verification(
        question="Does this replacement meet the original task’s requirements?",
        candidate_source=(
            "def remove_duplicates(values):\n"
            "    result = []\n"
            "    for item in values:\n"
            "        if item not in result:\n"
            "            result.append(item)\n"
            "    return result\n"
        ),
        choices=("Meets the task", "Does not meet the task", "Not sure"),
        answer="Meets the task",
        rationale=(
            "Items are visited in input order and appended only on their first "
            "occurrence. The separate result list preserves first-seen order, "
            "removes duplicates and leaves the input unchanged, including for "
            "empty input."
        ),
    ),
)


_EXAMPLES = (_LIST_APPEND, _AVERAGE, _REMOVE_DUPLICATES)


def list_examples() -> tuple[Example, ...]:
    return _EXAMPLES


def get_example(example_id: str) -> Example:
    """Look up an approved example; raise KeyError for unknown IDs."""
    for example in _EXAMPLES:
        if example.id == example_id:
            return example
    raise KeyError(f"Unknown example ID: {example_id!r}")
