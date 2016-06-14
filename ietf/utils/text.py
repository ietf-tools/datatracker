def skip_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix):]
    else:
        return text

def skip_suffix(text, prefix):
    if text.endswith(prefix):
        return text[:-len(prefix)]
    else:
        return text    
