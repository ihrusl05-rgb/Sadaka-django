import pytest

from apps.content.models import ContentItem
from apps.mosques.models import Mosque
from apps.projects.models import Project
from tests.factories import MosqueFactory, UserFactory


@pytest.mark.django_db
def test_mosque_slug_is_generated_and_updated():
    mosque = Mosque.objects.create(
        name="Мечеть Нур",
        description="Desc",
        city="Kazan",
        address="Addr",
        contact_email="mosque@example.com",
        contact_phone="+79990000001",
    )
    assert mosque.slug == "mechet-nur"

    mosque.name = "Мечеть Нур 2"
    mosque.slug = "manual-slug"
    mosque.save()
    mosque.refresh_from_db()

    assert mosque.slug == "mechet-nur-2"


@pytest.mark.django_db
def test_project_slug_is_unique_and_stable_on_self_update():
    mosque = MosqueFactory()
    creator = UserFactory(role="mosque_admin")
    first = Project.objects.create(
        mosque=mosque,
        created_by=creator,
        title="Ремонт крыши",
        description="Desc",
        goal_amount="1000.00",
    )
    second = Project.objects.create(
        mosque=mosque,
        created_by=creator,
        title="Ремонт крыши",
        description="Desc",
        goal_amount="2000.00",
    )

    assert first.slug == "remont-kryshi"
    assert second.slug == "remont-kryshi-2"

    first.description = "Updated"
    first.save()
    first.refresh_from_db()

    assert first.slug == "remont-kryshi"


@pytest.mark.django_db
def test_content_slug_overrides_manual_value():
    item = ContentItem.objects.create(
        title="Новости платформы",
        slug="custom-slug",
        body="Body",
        type=ContentItem.Type.NEWS,
    )

    assert item.slug == "novosti-platformy"

    item.title = "Новости платформы 2"
    item.slug = "another-manual-slug"
    item.save()
    item.refresh_from_db()

    assert item.slug == "novosti-platformy-2"
