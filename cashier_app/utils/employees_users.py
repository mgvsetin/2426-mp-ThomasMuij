"""Pomocné funkce pro validaci a správu údajů zaměstnanců a uživatelů."""

from cashier_app.db import get_pool
import re
import unicodedata
import string
from typing import List, Tuple
from email_validator import validate_email as _validate_email, EmailNotValidError
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
from phonenumbers import PhoneNumberFormat, national_significant_number

def is_manager(employee_id, event_id):
    """Zjistí, zda je zaměstnanec manažerem dané akce.

    Args:
        employee_id: ID zaměstnance.
        event_id: ID akce.

    Returns:
        True, pokud je zaměstnanec manažerem akce, jinak False.
    """
    is_manager = False
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            is_manager = bool(cur.execute('''
                SELECT 1
                FROM employee_event_booth_roles
                WHERE employee_id = %s
                AND event_id = %s
                AND booth_id IS NULL''',
                (employee_id, event_id)).fetchone())

    return is_manager


def validate_username(
    username: str,
    min_len: int = 3,
    max_len: int = 40,
    allow_chars: str = '._-',
    forbid_all_numeric: bool = False,
    forbidden_substrings: List[str] | None = None
    ) -> Tuple[bool, List[str]]:
    """
    Validuje uživatelské jméno.

    Pravidla (výchozí):
      - délka mezi min_len a max_len
      - začíná a končí alfanumerickým znakem
      - prostřední znaky mohou obsahovat písmena, číslice a znaky z allow_chars
      - žádné po sobě jdoucí speciální znaky z allow_chars (např. ".." nebo "._")
      - volitelně zakázat uživatelská jména, která jsou celá číselná
      - volitelně zakázat určité podřetězce (bez ohledu na velikost písmen)

    Returns:
      (is_valid, errors)

    Možné chybové zprávy (může jich být vráceno více):
    - "username must be a string"
    - "username must be at least {min_len} characters"
    - "username must be at most {max_len} characters"
    - "username must start and end with a letter or digit, and may only contain letters, digits, and these characters: {allow_chars}"
    - "username must not contain consecutive characters from '{allow_chars}'"
    - "username must not be all numeric"
    - "username must not contain the reserved words: {substring}"
    """

    errors: List[str] = []
    if not isinstance(username, str):
        return False, ["username must be a string"]

    username = unicodedata.normalize("NFC", username)
    username = username.strip()
    if len(username) < min_len:
        errors.append(f"username must be at least {min_len} characters")
    if len(username) > max_len:
        errors.append(f"username must be at most {max_len} characters")

    # Vytvoř třídu povolených znaků (písmena, čísla,...)
    esc = re.escape(allow_chars)
    # ASCII písmena + číslice + Latin-1 + Latin-Extended-A
    char_class = r"A-Za-z0-9\u00C0-\u017F"
    pattern = rf"^[A-Za-z0-9](?:[A-Za-z0-9{esc}]{{0,{max_len-2}}})[A-Za-z0-9]$" if max_len >= 2 else r"^[A-Za-z0-9]$"
    if max_len >= 2:
        pattern = f"^[{char_class}](?:[{char_class}{esc}]{{0,{max_len-2}}})[{char_class}]$"
    else:
        pattern = f"^[{char_class}]$"
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
    Validuje e-mailovou adresu.

    Returns:
      (is_valid, errors)

    Možné chybové zprávy (může jich být vráceno více):
    - "email must be a string"
    - "email is empty"
    - chybové zprávy vyvolané email_validator.EmailNotValidError
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


def validate_new_password(
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
    Validuje heslo s nastavitelnými pravidly.

    Výchozí pravidla:
      - alespoň min_len znaků
      - obsahuje velké písmeno, malé písmeno, číslici a speciální znak (jeden z string.punctuation)
      - žádné mezery (volitelné)
      - není zakázané (běžné) heslo
      - neobsahuje uživatelské jméno ani lokální část e-mailu (pokud jsou zadány)

    Returns:
      (is_valid, errors)

    Možné chybové zprávy (může jich být vráceno více):
    - "password must be a string"
    - "password is empty"
    - "password must be at least {min_len} characters long"
    - "password must not contain spaces or tabs"
    - "password must contain at least one uppercase letter"
    - "password must contain at least one lowercase letter"
    - "password must contain at least one digit"
    - "password must contain at least one special character (e.g. !@#$%)"
    - "password is too common or easily guessed"
    - "password must not contain the username"
    - "password must not contain the email local-part"
    - "password contains too many repeated characters in sequence"
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


def validate_first_or_last_name(
    name: str,
    min_len: int = 1,
    max_len: int = 100,
    allow_chars: str = '._-',
    forbid_all_numeric: bool = False,
    forbidden_substrings: List[str] | None = None
    ) -> Tuple[bool, List[str]]:
    """
    Validuje křestní jméno nebo příjmení.

    Není příliš přísná (povoluje číslice,...).

    Pravidla (výchozí):
      - délka mezi min_len a max_len
      - znaky mohou obsahovat písmena, číslice a znaky z allow_chars
      - volitelně zakázat jména, která jsou celá číselná
      - volitelně zakázat určité podřetězce (bez ohledu na velikost písmen)

    Returns:
      (is_valid, errors)

    Možné chybové zprávy (může jich být vráceno více):
    - "name must be a string"
    - "name must be at least {min_len} characters"
    - "name must be at most {max_len} characters"
    - "name may only contain letters, digits, and these characters: {allow_chars}"
    - "name must not be all numeric"
    - "name must not contain the reserved word: {substring}"
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

    # Sestav třídu povolených znaků (písmena, číslice, Latin-1 + Latin-Extended-A)
    esc = re.escape(allow_chars)
    char_class = r"A-Za-z0-9\u00C0-\u017F"

    # Ověř, že každý znak je povolený. Délka je již zkontrolována výše,
    # takže u prázdného řetězce tuto kontrolu přeskoč (zachytí ji kontrola délky).
    if name:
        allowed_pattern = f"^[{char_class}{esc}]+$"
        if not re.match(allowed_pattern, name):
            errors.append(f"name may only contain letters, digits, and these characters: {allow_chars}")

    if forbid_all_numeric and name.isdigit():
        errors.append("name must not be all numeric")

    if forbidden_substrings:
        low = name.lower()
        for s in forbidden_substrings:
            if s and s.lower() in low:
                errors.append(f"name must not contain the reserved word: {s}")

    return (len(errors) == 0), errors


def validate_phone_number(phone_number: str) -> bool:
    """
    Validuje telefonní číslo s kódem země.

    Returns:
      is_valid
    """
    try:
        phone_number_instance = phonenumbers.parse(str(phone_number))
    except NumberParseException as e:
        return False

    if not phonenumbers.is_possible_number(phone_number_instance):
        return False

    if not phonenumbers.is_valid_number(phone_number_instance):
        return False

    return True


def format_valid_phone_number(phone_number: str) -> dict[str]:
    """
    Naformátuje platné telefonní číslo s kódem země.

    Returns:
      {
        'e164': formát E.164,
        'international': mezinárodní formát,
        'national': národní formát,
        'national_significant_number': telefonní číslo bez kódu země,
        'country_code': +kód země telefonního čísla
      }
    """
    phone_number_instance = phonenumbers.parse(str(phone_number))

    e164 = phonenumbers.format_number(phone_number_instance, PhoneNumberFormat.E164)
    international = phonenumbers.format_number(phone_number_instance, PhoneNumberFormat.INTERNATIONAL)
    national = phonenumbers.format_number(phone_number_instance, PhoneNumberFormat.NATIONAL)
    nsn = national_significant_number(phone_number_instance)
    country_code = phone_number_instance.country_code

    return {
        'e164': e164,
        'international': international,
        'national': national,
        'national_significant_number': nsn,
        'country_code': f'+{country_code}'
    }


def add_more_phone_number_info(users):
    """Doplní ke každému uživateli v seznamu rozšířené informace o telefonním čísle.

    Pro každého uživatele přidá formáty: e164, mezinárodní, národní,
    národní významné číslo a kód země.

    Args:
        users: Seznam slovníků uživatelů s klíčem 'phone_number'.
    """
    for user in users:
        phone_number_formats = {
            'e164': None,
            'international': None,
            'national': None,
            'national_significant_number': None,
            'country_code': None
        }
        if user['phone_number']:
            phone_number_formats = format_valid_phone_number(user['phone_number'])

        user['phone_number'] = phone_number_formats['e164'] # už by mělo být
        user['phone_number_international'] = phone_number_formats['international']
        user['phone_number_national'] = phone_number_formats['national']
        user['phone_number_national_significant_number'] = phone_number_formats['national_significant_number']
        user['phone_number_country_code'] = phone_number_formats['country_code']


def validate_other_identifier(
    other_identifier: str,
    min_len: int = 1,
    max_len: int = 100,
    forbidden_substrings: List[str] | None = None
    ) -> Tuple[bool, List[str]]:
    """
    Validuje other_identifier (jiný identifikátor).

    Pravidla (výchozí):
      - délka mezi min_len a max_len
      - volitelně zakázat určité podřetězce (bez ohledu na velikost písmen)

    Returns:
      (is_valid, errors)

    Možné chybové zprávy (může jich být vráceno více):
    - "other_identifier must be at least {min_len} characters"
    - "other_identifier must be at most {max_len} characters"
    - "other_identifier must not contain the reserved word: {substring}"
    """

    errors: List[str] = []

    other_identifier = unicodedata.normalize("NFC", str(other_identifier))
    other_identifier = other_identifier.strip()

    if len(other_identifier) < min_len:
        errors.append(f"other_identifier must be at least {min_len} characters")
    if len(other_identifier) > max_len:
        errors.append(f"other_identifier must be at most {max_len} characters")

    if forbidden_substrings:
        low = other_identifier.lower()
        for s in forbidden_substrings:
            if s and s.lower() in low:
                errors.append(f"other_identifier must not contain the reserved word: {s}")

    return (len(errors) == 0), errors