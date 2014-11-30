def insert_after_in_ordered_dict(dictionary, key, value, after):
    # there's no insert in ordered dict so re-add entries after confirm_acronym instead
    dictionary[key] = value

    reorder = False
    l = dictionary.items() # don't mutate the dict while looping
    for k, v in l:
        if reorder and k != key:
            del dictionary[k]
            dictionary[k] = v

        if k == after:
            reorder = True
