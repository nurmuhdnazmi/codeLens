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


_EXAMPLE = Example(
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


def get_example(example_id: str) -> Example:
    """Look up an approved example; raise KeyError for unknown IDs."""
    if example_id != _EXAMPLE.id:
        raise KeyError(f"Unknown example ID: {example_id!r}")
    return _EXAMPLE
