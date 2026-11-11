from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Example:
    id: str
    title: str
    task: str
    source: str


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
)


def get_example(example_id: str) -> Example:
    """Look up an approved example; raise KeyError for unknown IDs."""
    if example_id != _EXAMPLE.id:
        raise KeyError(f"Unknown example ID: {example_id!r}")
    return _EXAMPLE
