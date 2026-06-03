import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.content.admin import ContentItemAdmin
from apps.content.models import ContentItem
from apps.mosques.admin import MosqueAdmin
from apps.mosques.models import Mosque
from apps.projects.admin import ProjectAdmin
from apps.projects.models import Project
from tests.factories import UserFactory


@pytest.mark.django_db
def test_slug_prepopulated_fields_are_configured():
    assert MosqueAdmin.prepopulated_fields == {"slug": ("name",)}
    assert ProjectAdmin.prepopulated_fields == {"slug": ("title",)}
    assert ContentItemAdmin.prepopulated_fields == {"slug": ("title",)}


@pytest.mark.django_db
def test_slug_field_has_admin_help_text():
    request = RequestFactory().get("/")
    request.user = UserFactory(role="platform_admin", is_staff=True)

    mosque_admin = MosqueAdmin(Mosque, AdminSite())
    project_admin = ProjectAdmin(Project, AdminSite())
    content_admin = ContentItemAdmin(ContentItem, AdminSite())

    mosque_form = mosque_admin.get_form(request)
    project_form = project_admin.get_form(request)
    content_form = content_admin.get_form(request)

    expected = "Слаг подставляется автоматически из названия и будет пересчитан при сохранении."
    assert mosque_form.base_fields["slug"].help_text == expected
    assert project_form.base_fields["slug"].help_text == expected
    assert content_form.base_fields["slug"].help_text == expected
