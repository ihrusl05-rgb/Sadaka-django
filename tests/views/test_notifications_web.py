import pytest
from django.urls import reverse

from apps.notifications.models import Notification
from tests.factories import UserFactory


@pytest.mark.django_db
def test_notifications_page_requires_authentication(client):
    response = client.get("/profile/notifications/")

    assert response.status_code == 302
    assert reverse("platform:login") in response.url


@pytest.mark.django_db
def test_notifications_page_renders_only_current_user_notifications(client):
    user = UserFactory(email="user@example.com")
    other_user = UserFactory(email="other@example.com")
    Notification.objects.create(
        user=user,
        title="Ваше уведомление",
        message="Только для текущего пользователя",
        event=Notification.Event.PROFILE_UPDATED,
        notification_type=Notification.NotificationType.INFO,
    )
    Notification.objects.create(
        user=other_user,
        title="Чужое уведомление",
        message="Не должно быть видно",
        event=Notification.Event.PROFILE_UPDATED,
        notification_type=Notification.NotificationType.INFO,
    )

    client.force_login(user)
    response = client.get("/profile/notifications/")
    html = response.content.decode()

    assert response.status_code == 200
    assert "Ваше уведомление" in html
    assert "Чужое уведомление" not in html


@pytest.mark.django_db
def test_notifications_api_unread_count_and_read_all(client):
    user = UserFactory(email="user@example.com")
    Notification.objects.create(
        user=user,
        title="Первое",
        message="Текст",
        event=Notification.Event.DONATION_SUCCESS,
        notification_type=Notification.NotificationType.SUCCESS,
    )
    Notification.objects.create(
        user=user,
        title="Второе",
        message="Текст",
        event=Notification.Event.DONATION_SUCCESS,
        notification_type=Notification.NotificationType.SUCCESS,
    )

    client.force_login(user)
    unread_response = client.get("/api/notifications/unread-count/")
    assert unread_response.status_code == 200
    assert unread_response.json()["count"] == 2

    read_all_response = client.post("/api/notifications/read-all/", content_type="application/json")
    assert read_all_response.status_code == 200
    assert read_all_response.json()["updated"] == 2

    unread_after_response = client.get("/api/notifications/unread-count/")
    assert unread_after_response.json()["count"] == 0


@pytest.mark.django_db
def test_notifications_api_allows_deleting_own_notification(client):
    user = UserFactory(email="user@example.com")
    notification = Notification.objects.create(
        user=user,
        title="Удалить",
        message="Текст",
        event=Notification.Event.PROFILE_UPDATED,
        notification_type=Notification.NotificationType.INFO,
    )

    client.force_login(user)
    response = client.post(f"/api/notifications/{notification.id}/delete/", content_type="application/json")

    assert response.status_code == 200
    notification.refresh_from_db()
    assert notification.is_deleted is True


@pytest.mark.django_db
def test_notifications_test_endpoint_is_available_for_staff(client):
    user = UserFactory(email="staff@example.com", role="platform_admin")
    client.force_login(user)

    response = client.post("/api/notifications/test/", content_type="application/json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert Notification.objects.filter(user=user, event=Notification.Event.TEST).exists()


@pytest.mark.django_db
def test_notifications_test_endpoint_is_forbidden_for_regular_user(client):
    user = UserFactory(email="plain@example.com")
    client.force_login(user)

    response = client.post("/api/notifications/test/", content_type="application/json")

    assert response.status_code == 403
