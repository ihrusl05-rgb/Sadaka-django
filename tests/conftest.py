import pytest
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def platform_admin():
    return UserFactory(role="platform_admin", is_staff=True)


@pytest.fixture
def mosque_admin():
    return UserFactory(role="mosque_admin")
