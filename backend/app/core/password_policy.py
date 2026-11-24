import re

BANNED_WORDS = (
    "password", "passw0rd", "qwerty", "letmein", "welcome",
    "admin", "iloveyou", "stockdash",
)
SEQUENCES = (
    "abcdefghijklmnopqrstuvwxyz", "zyxwvutsrqponmlkjihgfedcba",
    "0123456789", "9876543210",
    "qwertyuiop", "poiuytrewq", "asdfghjkl", "lkjhgfdsa", "zxcvbnm", "mnbvcxz",
)


def _has_sequence(text: str, length: int = 4) -> bool:
    return any(
        seq[i : i + length] in text
        for seq in SEQUENCES
        for i in range(len(seq) - length + 1)
    )


def validate_password(password: str, email: str) -> list[str]:
    errors: list[str] = []
    if len(password) < 8:
        errors.append("At least 8 characters required.")
    if len(password.encode("utf-8")) > 72:
        errors.append("At most 72 bytes allowed.")
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        errors.append("Must contain letters and digits.")
    low = password.lower()
    if any(word in low for word in BANNED_WORDS):
        errors.append("Contains a common word or pattern.")
    if _has_sequence(low):
        errors.append("Must not contain sequences like abcd or 1234.")
    if re.search(r"(.)\1{2,}", low):
        errors.append("Must not repeat a character 3+ times in a row.")
    if re.fullmatch(r"(.+?)\1+", low):
        errors.append("Must not be a repeated block.")
    local = email.split("@")[0].lower()
    if len(local) >= 3 and local in low:
        errors.append("Must not contain your email name.")
    return errors