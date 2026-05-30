import pytest
from adds.selection_sort import selection_sort


def test_empty_list():
    assert selection_sort([]) == []


def test_single_element():
    assert selection_sort([1]) == [1]


def test_already_sorted():
    assert selection_sort([1, 2, 3]) == [1, 2, 3]


def test_reverse_sorted():
    assert selection_sort([3, 2, 1]) == [1, 2, 3]


def test_duplicates():
    assert selection_sort([3, 1, 2, 1]) == [1, 1, 2, 3]


def test_negative_numbers():
    assert selection_sort([-1, 3, -2]) == [-2, -1, 3]


def test_input_immutability():
    original = [3, 1, 2]
    snapshot = list(original)
    selection_sort(original)
    assert original == snapshot
