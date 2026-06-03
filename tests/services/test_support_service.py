import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.support.models import SupportMessage, SupportTicket, SupportUser
from apps.support.services import SupportActor, SupportService


@pytest.mark.django_db
def test_receive_user_message_creates_support_entities():
    actor = SupportActor(telegram_id=7776808886, username="gergiw", first_name="R")

    ticket, message, created_ticket = SupportService.receive_user_message(actor=actor, text="Здравствуйте")

    assert created_ticket is True
    assert ticket.status == SupportTicket.Status.NEW
    assert message.sender_type == SupportMessage.SenderType.USER
    assert SupportUser.objects.filter(telegram_user_id=actor.telegram_id).exists()


@pytest.mark.django_db
def test_receive_user_message_reuses_open_ticket_and_reopens_answered_status():
    user_actor = SupportActor(telegram_id=123456789, username="madina", first_name="Мадина")
    admin_actor = SupportActor(telegram_id=999, username="admin")
    ticket, _, _ = SupportService.receive_user_message(actor=user_actor, text="Первый вопрос")
    SupportService.send_admin_reply(ticket=ticket, admin=admin_actor, text="Здравствуйте")

    reused_ticket, message, created_ticket = SupportService.receive_user_message(actor=user_actor, text="Ещё вопрос")

    reused_ticket.refresh_from_db()
    assert created_ticket is False
    assert reused_ticket.id == ticket.id
    assert reused_ticket.status == SupportTicket.Status.IN_PROGRESS
    assert message.text == "Ещё вопрос"


@pytest.mark.django_db
def test_send_admin_reply_marks_ticket_answered_and_sets_first_reply_time():
    user_actor = SupportActor(telegram_id=555666777, username="ibrahim")
    admin_actor = SupportActor(telegram_id=42, username="operator")
    ticket, _, _ = SupportService.receive_user_message(actor=user_actor, text="Нужна помощь")

    reply = SupportService.send_admin_reply(ticket=ticket, admin=admin_actor, text="Поможем")

    ticket.refresh_from_db()
    assert reply.sender_type == SupportMessage.SenderType.ADMIN
    assert ticket.status == SupportTicket.Status.ANSWERED
    assert ticket.assigned_admin_id == admin_actor.telegram_id
    assert ticket.first_admin_replied_at is not None


@pytest.mark.django_db
def test_close_ticket_and_new_user_message_creates_new_ticket():
    user_actor = SupportActor(telegram_id=111222333, username="umar")
    admin_actor = SupportActor(telegram_id=43, username="closer")
    first_ticket, _, _ = SupportService.receive_user_message(actor=user_actor, text="Первое обращение")

    SupportService.close_ticket(ticket=first_ticket, admin=admin_actor)
    second_ticket, _, created_ticket = SupportService.receive_user_message(actor=user_actor, text="Новое обращение")

    first_ticket.refresh_from_db()
    assert first_ticket.status == SupportTicket.Status.CLOSED
    assert created_ticket is True
    assert second_ticket.id != first_ticket.id


@pytest.mark.django_db
def test_blocked_user_cannot_send_message():
    support_user = SupportUser.objects.create(
        telegram_user_id=777,
        username="blocked",
        first_name="Blocked",
        last_name="",
        is_blocked=True,
        first_seen_at=timezone.now(),
        last_seen_at=timezone.now(),
    )
    actor = SupportActor(telegram_id=support_user.telegram_user_id, username=support_user.username)

    with pytest.raises(ValidationError, match="Недоступно"):
        SupportService.receive_user_message(actor=actor, text="Пустите")


@pytest.mark.django_db
def test_serialized_views_and_analytics_return_expected_data():
    user_actor = SupportActor(telegram_id=888999000, username="fatima", first_name="Фатима")
    admin_actor = SupportActor(telegram_id=55, username="admin55")
    ticket, _, _ = SupportService.receive_user_message(actor=user_actor, text="Вопрос по проекту")
    SupportService.assign_ticket(ticket=ticket, admin=admin_actor)
    SupportService.send_admin_reply(ticket=ticket, admin=admin_actor, text="Ответили")

    listing = SupportService.list_tickets(scope="active", page=1)
    ticket_snapshot = SupportService.get_ticket_snapshot(ticket_id=ticket.id)
    profile = SupportService.get_user_profile(support_user_id=ticket.support_user_id)
    analytics = SupportService.get_analytics()

    assert listing["items"][0]["id"] == ticket.id
    assert ticket_snapshot["messages"][-1]["text"] == "Ответили"
    assert profile["tickets_total"] == 1
    assert analytics["totals"]["all"] >= 1
