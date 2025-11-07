from cashier_app.db import get_db
import re
import string
from typing import List, Tuple
from email_validator import validate_email as _validate_email, EmailNotValidError

def is_manager(employee, event):
    conn = get_db()
    is_manager = False
    with conn.transaction():
        with conn.cursor() as cur:
            is_manager = bool(cur.execute('''
                SELECT 1
                FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s
                AND booth_id IS NULL''',
                (employee['id'], event['id'])).fetchone())
            
    return is_manager


def validate_username(
    username: str,
    min_len: int = 3,
    max_len: int = 30,
    allow_chars: str = '._-',
    forbid_all_numeric: bool = False,
    forbidden_substrings: List[str] | None = None
    ) -> Tuple[bool, List[str]]:
    """
    Validate a username.

    Rules (defaults):
      - length between min_len and max_len
      - starts and ends with an alphanumeric character
      - middle characters may include letters, digits, and characters in allow_chars
      - no consecutive punctuation from allow_chars (e.g., ".." or "._")
      - optionally forbid usernames that are entirely numeric
      - optionally forbid certain substrings (case-insensitive)

    Returns:
      (is_valid, errors)
    """

    errors: List[str] = []
    if not isinstance(username, str):
        return False, ["username must be a string"]

    username = username.strip()
    if len(username) < min_len:
        errors.append(f"username must be at least {min_len} characters")
    if len(username) > max_len:
        errors.append(f"username must be at most {max_len} characters")

    # Vytvoř třídu povolených znaků (písmena, čísla,...)
    esc = re.escape(allow_chars)
    pattern = rf"^[A-Za-z0-9](?:[A-Za-z0-9{esc}]{{0,{max_len-2}}})[A-Za-z0-9]$" if max_len >= 2 else r"^[A-Za-z0-9]$"
    if not re.match(pattern, username):
        errors.append(
            "username must start and end with a letter or digit, "
            f"and may only contain letters, digits, and these characters: {allow_chars}"
        )

    # Žádné po sobě následující speciální znaky
    if allow_chars:
        seq_pattern = "[" + re.escape(allow_chars) + r"]{2,}"
        if re.search(seq_pattern, username):
            errors.append(f"username must not contain consecutive characters from {allow_chars!r}")

    if forbid_all_numeric and username.isdigit():
        errors.append("username must not be all numeric")

    if forbidden_substrings:
        low = username.lower()
        for s in forbidden_substrings:
            if s and s.lower() in low:
                errors.append(f"username must not contain the reserved word: {s}")

    return (len(errors) == 0), errors


def validate_email(email: str) -> Tuple[bool, List[str]]:
    """
    Validate an email address.

    Returns:
      (is_valid, errors)
    """
    errors: List[str] = []
    if not isinstance(email, str):
        return False, ["email must be a string"]
    email = email.strip()

    if not email:
        return False, ["email is empty"]

    try:
        _validate_email(email, check_deliverability=False)
    except EmailNotValidError as e:
        errors.append(str(e))

    return (len(errors) == 0), errors


def validate_password(
    password: str,
    min_len: int = 8,
    require_upper: bool = True,
    require_lower: bool = True,
    require_digit: bool = True,
    require_special: bool = True,
    forbid_spaces: bool = True,
    forbidden_passwords: List[str] | None = None,
    username: str | None = None,
    email: str | None = None,
) -> Tuple[bool, List[str]]:
    """
    Validate a password with configurable rules.

    Default rules:
      - at least min_len characters
      - contains uppercase, lowercase, digit, and a special character (one of string.punctuation)
      - no spaces (optional)
      - not a forbidden (common) password
      - not containing the username or the local part of the email (if provided)

    Returns:
      (is_valid, errors)
    """
    errors: List[str] = []
    if not isinstance(password, str):
        return False, ["password must be a string"]
    if password is None or password == "":
        return False, ["password is empty"]

    if len(password) < min_len:
        errors.append(f"password must be at least {min_len} characters long")

    if forbid_spaces and (" " in password or "\t" in password):
        errors.append("password must not contain spaces or tabs")

    if require_upper and not re.search(r"[A-Z]", password):
        errors.append("password must contain at least one uppercase letter")
    if require_lower and not re.search(r"[a-z]", password):
        errors.append("password must contain at least one lowercase letter")
    if require_digit and not re.search(r"[0-9]", password):
        errors.append("password must contain at least one digit")
    if require_special and not re.search(rf"[{re.escape(string.punctuation)}]", password):
        errors.append("password must contain at least one special character (e.g. !@#$%)")

    pw_lower = password.lower()
    if forbidden_passwords is None:
        forbidden_passwords = []

    forbidden_passwords = {p.lower() for p in forbidden_passwords}
    if pw_lower in forbidden_passwords:
        errors.append("password is too common or easily guessed")

    if username:
        if username.strip() and username.lower() in pw_lower:
            errors.append("password must not contain the username")
    if email:
        local = email.split("@", 1)[0] if "@" in email else ""
        if local and local.lower() in pw_lower:
            errors.append("password must not contain the email local-part")

    if re.search(r"(.)\1{5,}", password):
        errors.append("password contains too many repeated characters in sequence")

    return (len(errors) == 0), errors