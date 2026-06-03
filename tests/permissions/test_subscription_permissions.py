import pytest

from apps.subscriptions.permissions import SubscriptionAccessPermission
from tests.factories import MosqueFactory, MosqueMembershipFactory, UserFactory
from apps.subscriptions.models import Subscription


@pytest.mark.django_db
def test_regular_user_only_accesses_own_subscription(rf):
    owner = UserFactory()
    other_user = UserFactory()
    mosque = MosqueFactory()
    subscription = Subscription.objects.create(user=owner, mosque=mosque, amount="100.00")
    request = rf.get("/")
    request.user = other_user

    permission = SubscriptionAccessPermission()

    assert permission.has_object_permission(request, None, subscription) is False
