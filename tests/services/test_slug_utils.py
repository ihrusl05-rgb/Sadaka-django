import pytest

from apps.content.models import ContentItem
from apps.mosques.models import Mosque
from common.utils.slugs import generate_unique_slug, transliterate_to_ascii


@pytest.mark.django_db
def test_transliterate_to_ascii_handles_cyrillic():
    assert transliterate_to_ascii("Мечеть Нур") == "Mechet Nur"


@pytest.mark.django_db
def test_generate_unique_slug_for_latin_and_collisions():
    Mosque.objects.create(
        name="Central Mosque",
        description="Desc",
        city="Kazan",
        address="Addr",
        contact_email="one@example.com",
        contact_phone="+79990000001",
    )

    first = generate_unique_slug(source_value="Central Mosque", model=Mosque)
    second = generate_unique_slug(source_value="Central Mosque", model=Mosque, fallback_base="mosque")

    assert first == "central-mosque-2"
    assert second == "central-mosque-2"


@pytest.mark.django_db
def test_generate_unique_slug_for_cyrillic_and_fallback():
    slug = generate_unique_slug(source_value="Ремонт крыши", model=ContentItem)
    fallback = generate_unique_slug(source_value="!!!", model=ContentItem)

    assert slug == "remont-kryshi"
    assert fallback == "content-item"
