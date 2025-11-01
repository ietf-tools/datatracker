# Copyright The IETF Trust 2025, All Rights Reserved
import unicodedata

def normalize_for_sorting(text):
    """Normalize text for proper accent-aware sorting."""
    # NFD decomposes accented characters but keeps them sortable
    return unicodedata.normalize('NFD', text.lower())
