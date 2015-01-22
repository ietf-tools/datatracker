def insert_after_in_ordered_dict(dictionary, key, value, after):
    """There's no "insert" in ordered dict so simulate it instead by
    re-adding entries. Obviously that's not ideal, but for small dicts the
    overhead is negligible."""
    dictionary[key] = value

    reorder = False
    l = dictionary.items() # don't mutate the dict while looping
    for k, v in l:
        if reorder and k != key:
            del dictionary[k]
            dictionary[k] = v

        if k == after:
            reorder = True
