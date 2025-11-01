# Copyright The IETF Trust 2025, All Rights Reserved
import unicodedata

def normalize_for_sorting(text):
    """Normalize text for proper accent-aware sorting."""
    # Normalize the text to NFD (decomposed form)
    decomposed = unicodedata.normalize('NFD', text)
    # Filter out combining diacritical marks
    return ''.join(char for char in decomposed if not unicodedata.combining(char))
