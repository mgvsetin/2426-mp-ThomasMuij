import re
import unicodedata
import string
from typing import List, Tuple
from email_validator import validate_email as _validate_email, EmailNotValidError


def validate_event_name(
    name: str,
    min_len: int = 3,
    max_len: int = 40,
    allow_chars: str = '._-',
    forbid_all_numeric: bool = False,
    forbidden_substrings: List[str] | None = None
    ) -> Tuple[bool, List[str]]:
    """
    Validate an event name.

    Rules (defaults):
      - length between min_len and max_len
      - starts and ends with an alphanumeric character
      - middle characters may include letters, digits, and characters in allow_chars
      - no consecutive punctuation from allow_chars (e.g., ".." or "._")
      - optionally forbid usernames that are entirely numeric
      - optionally forbid certain substrings (case-insensitive)

    Returns:
      (is_valid, errors)

    Possible error messages (one or more may be returned):
    - "name must be a string"
    - "name must be at least {min_len} characters"
    - "name must be at most {max_len} characters"
    - "name must start and end with a letter or digit, and may only contain letters, digits, and these characters: {allow_chars}"
    - "name must not contain consecutive characters from '{allow_chars}'"
    - "name must not be all numeric"
    - "name must not contain the reserved words: {substring}"
    """

    errors: List[str] = []
    if not isinstance(name, str):
        return False, ["name must be a string"]

    name = unicodedata.normalize("NFC", name)
    name = name.strip()
    if len(name) < min_len:
        errors.append(f"name must be at least {min_len} characters")
    if len(name) > max_len:
        errors.append(f"name must be at most {max_len} characters")

    # Vytvoř třídu povolených znaků (písmena, čísla,...)
    esc = re.escape(allow_chars)
    # ASCII písmena + číslice + Latin-1 + Latin-Extended-A
    char_class = r"A-Za-z0-9\u00C0-\u017F"
    pattern = rf"^[A-Za-z0-9](?:[A-Za-z0-9{esc}]{{0,{max_len-2}}})[A-Za-z0-9]$" if max_len >= 2 else r"^[A-Za-z0-9]$"
    if max_len >= 2:
        pattern = f"^[{char_class}](?:[{char_class}{esc}]{{0,{max_len-2}}})[{char_class}]$"
    else:
        pattern = f"^[{char_class}]$"
    if not re.match(pattern, name):
        errors.append(
            "name must start and end with a letter or digit, "
            f"and may only contain letters, digits, and these characters: {allow_chars}"
        )

    # Žádné po sobě následující speciální znaky
    if allow_chars:
        seq_pattern = "[" + re.escape(allow_chars) + r"]{2,}"
        if re.search(seq_pattern, name):
            errors.append(f"name must not contain consecutive characters from {allow_chars!r}")

    if forbid_all_numeric and name.isdigit():
        errors.append("name must not be all numeric")

    if forbidden_substrings:
        low = name.lower()
        for s in forbidden_substrings:
            if s and s.lower() in low:
                errors.append(f"name must not contain the reserved word: {s}")

    return (len(errors) == 0), errors

