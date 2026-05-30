def selection_sort(values):
    """Return a sorted copy of values using selection sort. Input is unchanged."""
    result = list(values)
    n = len(result)
    for i in range(n):
        min_idx = i
        for j in range(i, n):
            if result[j] < result[min_idx]:
                min_idx = j
        result[i], result[min_idx] = result[min_idx], result[i]
    return result
