from decimal import Decimal

import pytest

from apps.notifications.models import Notification
from apps.platform.models import MosqueSiteRequest
from apps.projects.models import Project
from apps.users.telegram_bot import SadakaTelegramBotService
from tests.factories import MosqueFactory, MosqueMembershipFactory, ProjectFactory, TelegramAccountFactory, UserFactory


@pytest.mark.django_db
def test_sadaka_telegram_bot_service_status_notifications_requests_and_projects_are_scoped_to_linked_user():
    user = UserFactory(email="telegram_user@example.com", phone="+79990001122", role="mosque_admin")
    other_user = UserFactory(email="other@example.com", phone="+79990001133")
    TelegramAccountFactory(user=user, telegram_id=123456789, username="sadaka_user")
    TelegramAccountFactory(user=other_user, telegram_id=987654321, username="other_user")

    mosque = MosqueFactory(name="Нур")
    MosqueMembershipFactory(mosque=mosque, user=user)
    project = ProjectFactory(
        mosque=mosque,
        created_by=user,
        title="Ремонт мечети",
        status=Project.Status.PENDING,
        goal_amount=Decimal("250000.00"),
        current_amount=Decimal("15000.00"),
    )

    Notification.objects.create(
        user=user,
        title="Уведомление пользователя",
        message="Только для связанного пользователя",
        event=Notification.Event.PROJECT_SUBMITTED,
    )
    Notification.objects.create(
        user=other_user,
        title="Чужое уведомление",
        message="Не должно попадать в выборку",
        event=Notification.Event.PROJECT_SUBMITTED,
    )

    MosqueSiteRequest.objects.create(
        request_type=MosqueSiteRequest.RequestType.WIDGET_FORM,
        status=MosqueSiteRequest.Status.IN_PROGRESS,
        full_name="Ильдар",
        mosque_name="Новая мечеть",
        city="Уфа",
        phone=user.phone,
        comment="Ждём обратную связь",
        source="site_widget",
    )
    MosqueSiteRequest.objects.create(
        request_type=MosqueSiteRequest.RequestType.WIDGET_FORM,
        status=MosqueSiteRequest.Status.NEW,
        full_name="Другой",
        mosque_name="Чужая мечеть",
        city="Казань",
        phone=other_user.phone,
        source="site_widget",
    )

    payload = SadakaTelegramBotService.build_status_payload(telegram_id=123456789)
    notifications = list(SadakaTelegramBotService.recent_notifications(telegram_id=123456789))
    requests = list(SadakaTelegramBotService.recent_requests(telegram_id=123456789))
    projects = list(SadakaTelegramBotService.recent_projects(telegram_id=123456789))

    assert payload["is_linked"] is True
    assert payload["notifications_total"] == 1
    assert payload["requests_total"] == 1
    assert payload["projects_total"] == 1
    assert notifications[0].title == "Уведомление пользователя"
    assert requests[0].mosque_name == "Новая мечеть"
    assert projects[0].title == project.title


@pytest.mark.django_db
def test_sadaka_telegram_bot_service_returns_unlinked_payload_for_unknown_telegram():
    payload = SadakaTelegramBotService.build_status_payload(telegram_id=555555555)

    assert payload["is_linked"] is False
    assert payload["notifications_total"] == 0
    assert payload["requests_total"] == 0
