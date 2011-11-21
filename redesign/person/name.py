def name_parts(name):
    prefix, first, middle, last, suffix = "", "", "", "", ""
    parts = name.split()
    if parts[0] in ["Mr", "Mr.", "Mrs", "Mrs.", "Ms", "Ms.", "Miss", "Dr.", "Doctor", "Prof", "Prof.", "Professor", "Sir", "Lady", "Dame"]:
        prefix = parts[0];
        parts = parts[1:]
    if len(parts) > 2:
        if parts[-1] in ["Jr", "Jr.", "II", "2nd", "III", "3rd", ]:
            suffix = parts[-1]
            parts = parts[:-1]
    if len(parts) > 2:
        first = parts[0]
        last = parts[-1]
        middle = " ".join(parts[1:-1])
    elif len(parts) == 2:
        first, last = parts
    else:
        last = parts[0]
    return prefix, first, middle, last, suffix
    
