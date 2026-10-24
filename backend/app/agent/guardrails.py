"""Input hygiene and prompt-injection signalling. User text is always treated as untrusted data."""
import re

MAX_USER_CHARS = 2000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_INJECTION = re.compile(
    r"(ignore (all |any |the )?(previous|prior|above) (instructions|rules)|system prompt|developer message|"
    r"you are now|act as (an? )?(admin|developer)|reveal (your )?(prompt|instructions)|override (the )?rules|"
    r"skip (the )?verification|without (asking|confirmation))", re.I)


def clean_user_text(text: str) -> str:
    return _CTRL.sub("", text).strip()[:MAX_USER_CHARS]


def injection_suspected(text: str) -> bool:
    return bool(_INJECTION.search(text))


def mask_value(key: str, value):
    """Mask contact details in anything that is persisted or shown in debug traces."""
    if not isinstance(value, str):
        return value
    k = key.lower()
    if "phone" in k or (k in {"lookup_value", "challenge_answer"} and re.fullmatch(r"[\d+\-\s()]{6,}", value)):
        d = re.sub(r"\D", "", value)
        return "*" * max(len(d) - 4, 0) + d[-4:]
    if "email" in k and "@" in value:
        local, _, dom = value.partition("@")
        return f"{local[:1]}***@{dom}"
    return value


def mask_args(args: dict) -> dict:
    return {k: mask_value(k, v) for k, v in args.items()}
