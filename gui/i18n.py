"""Language of the interface: English, or Uzbek (Cyrillic) translations of the same texts."""
from __future__ import annotations

LANGUAGES = {"en": "English", "uz": "Ўзбекча"}
_language = "en"


def set_language(code: str) -> None:
    global _language
    _language = code if code in LANGUAGES else "en"


def language() -> str:
    return _language


def tr(text: str) -> str:
    """The text in the current language (English when no translation exists)."""
    if _language == "uz":
        return UZ.get(text, text)
    return text


from .i18n_uz import UZ  # noqa: E402
