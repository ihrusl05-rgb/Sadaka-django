import re

from django.utils.text import slugify


CYRILLIC_TRANSLIT_MAP = str.maketrans(
    {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "j",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sh",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "є": "ye",
        "і": "i",
        "ї": "yi",
        "ґ": "g",
        "А": "A",
        "Б": "B",
        "В": "V",
        "Г": "G",
        "Д": "D",
        "Е": "E",
        "Ё": "Yo",
        "Ж": "Zh",
        "З": "Z",
        "И": "I",
        "Й": "J",
        "К": "K",
        "Л": "L",
        "М": "M",
        "Н": "N",
        "О": "O",
        "П": "P",
        "Р": "R",
        "С": "S",
        "Т": "T",
        "У": "U",
        "Ф": "F",
        "Х": "H",
        "Ц": "C",
        "Ч": "Ch",
        "Ш": "Sh",
        "Щ": "Sh",
        "Ъ": "",
        "Ы": "Y",
        "Ь": "",
        "Э": "E",
        "Ю": "Yu",
        "Я": "Ya",
        "Є": "Ye",
        "І": "I",
        "Ї": "Yi",
        "Ґ": "G",
    }
)


def transliterate_to_ascii(value: str | None) -> str:
    return (value or "").translate(CYRILLIC_TRANSLIT_MAP)


def camel_to_kebab(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", value).lower()


def build_slug_candidate(value: str | None, *, fallback: str) -> str:
    candidate = slugify(transliterate_to_ascii(value))
    return candidate or slugify(fallback) or "item"


def generate_unique_slug(*, source_value: str | None, model, slug_field: str = "slug", instance=None, fallback_base: str | None = None) -> str:
    slug_model_field = model._meta.get_field(slug_field)
    max_length = slug_model_field.max_length
    fallback = fallback_base or camel_to_kebab(model.__name__)
    base_slug = build_slug_candidate(source_value, fallback=fallback)[:max_length].strip("-") or fallback[:max_length].strip("-") or "item"

    manager = getattr(model, "all_objects", None) or model._default_manager
    queryset = manager.all()

    if instance is not None and getattr(instance, "pk", None):
        queryset = queryset.exclude(pk=instance.pk)

    if not queryset.filter(**{slug_field: base_slug}).exists():
        return base_slug

    index = 2
    while True:
        suffix = f"-{index}"
        trimmed_base = base_slug[: max_length - len(suffix)].rstrip("-")
        candidate = f"{trimmed_base}{suffix}"
        if not queryset.filter(**{slug_field: candidate}).exists():
            return candidate
        index += 1
