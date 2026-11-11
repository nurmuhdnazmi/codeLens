from dataclasses import FrozenInstanceError

import pytest


def test_lookup_returns_the_approved_example():
    from codelens.catalogue import get_example

    example = get_example("list_append")

    assert example.id == "list_append"
    assert example.title == "List append"
    assert example.task == (
        "Append an integer to a list and return it. Every call without a "
        "supplied list must start empty. When a list is supplied, update "
        "that same list."
    )
    assert example.source == (
        "def append_item(item, values=[]):\n"
        "    values.append(item)\n"
        "    return values\n"
        "\n"
        "print(append_item(1))\n"
        "print(append_item(2))\n"
        "print(append_item(3, []))\n"
        "print(append_item(4))\n"
    )


def test_example_fields_cannot_be_reassigned():
    from codelens.catalogue import get_example

    example = get_example("list_append")

    with pytest.raises(FrozenInstanceError):
        example.task = "Changed task"


@pytest.mark.parametrize("example_id", ["unknown", "", "average", "remove_duplicates"])
def test_unknown_ids_are_rejected(example_id):
    from codelens.catalogue import get_example

    with pytest.raises(KeyError):
        get_example(example_id)
