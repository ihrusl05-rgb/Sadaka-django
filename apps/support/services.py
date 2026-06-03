from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Subquery
from django.utils import timezone

from apps.support.models import SupportMessage, SupportTicket, SupportUser


@dataclass(frozen=True)
class SupportActor:
    telegram_id: int
    username: str = ""
    first_name: str = ""
    last_name: str = ""


class SupportService:
    LIST_PAGE_SIZE = 8

    @staticmethod
    def _clean_text(text: str) -> str:
        return "\n".join(line.rstrip() for line in (text or "").strip().splitlines()).strip()

    @staticmethod
    def _display_name(*, first_name: str, last_name: str, username: str, fallback: str) -> str:
        full_name = " ".join(part for part in [first_name.strip(), last_name.strip()] if part).strip()
        if full_name and username:
            return f"{full_name} (@{username})"
        if username:
            return f"@{username}"
        if full_name:
            return full_name
        return fallback

    @staticmethod
    def _admin_label(*, username: str, fallback_id: int | None = None) -> str:
        if username:
            return f"@{username}"
        if fallback_id:
            return str(fallback_id)
        return "—"

    @staticmethod
    def _serialize_message(message: SupportMessage) -> dict:
        sender_display = (
            "Пользователь"
            if message.sender_type == SupportMessage.SenderType.USER
            else "Админ"
            if message.sender_type == SupportMessage.SenderType.ADMIN
            else "Система"
        )
        return {
            "id": message.id,
            "sender_type": message.sender_type,
            "sender_display": sender_display,
            "sender_telegram_id": message.sender_telegram_id,
            "sender_username": message.sender_username,
            "text": message.text,
            "created_at": message.created_at,
        }

    @staticmethod
    def _serialize_ticket(ticket: SupportTicket, *, messages: list[SupportMessage] | None = None) -> dict:
        messages = messages if messages is not None else list(ticket.messages.all())
        last_message = messages[-1] if messages else None
        has_admin_reply = any(message.sender_type == SupportMessage.SenderType.ADMIN for message in messages)
        user_display_name = SupportService._display_name(
            first_name=ticket.first_name,
            last_name=ticket.last_name,
            username=ticket.username,
            fallback=str(ticket.telegram_user_id),
        )
        return {
            "id": ticket.id,
            "support_user_id": ticket.support_user_id,
            "telegram_user_id": ticket.telegram_user_id,
            "username": ticket.username,
            "first_name": ticket.first_name,
            "last_name": ticket.last_name,
            "user_display_name": user_display_name,
            "status": ticket.status,
            "status_label": ticket.get_status_display(),
            "assigned_admin_id": ticket.assigned_admin_id,
            "assigned_admin_username": ticket.assigned_admin_username,
            "assigned_admin_label": SupportService._admin_label(
                username=ticket.assigned_admin_username,
                fallback_id=ticket.assigned_admin_id,
            ),
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "closed_at": ticket.closed_at,
            "first_admin_replied_at": ticket.first_admin_replied_at,
            "last_message": last_message.text if last_message else "",
            "last_message_at": last_message.created_at if last_message else ticket.updated_at,
            "has_admin_reply": has_admin_reply,
            "messages": [SupportService._serialize_message(message) for message in messages],
        }

    @staticmethod
    def _serialize_ticket_summary(ticket: SupportTicket) -> dict:
        user_display_name = SupportService._display_name(
            first_name=ticket.first_name,
            last_name=ticket.last_name,
            username=ticket.username,
            fallback=str(ticket.telegram_user_id),
        )
        return {
            "id": ticket.id,
            "support_user_id": ticket.support_user_id,
            "telegram_user_id": ticket.telegram_user_id,
            "username": ticket.username,
            "first_name": ticket.first_name,
            "last_name": ticket.last_name,
            "user_display_name": user_display_name,
            "status": ticket.status,
            "status_label": ticket.get_status_display(),
            "assigned_admin_id": ticket.assigned_admin_id,
            "assigned_admin_username": ticket.assigned_admin_username,
            "assigned_admin_label": SupportService._admin_label(
                username=ticket.assigned_admin_username,
                fallback_id=ticket.assigned_admin_id,
            ),
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "closed_at": ticket.closed_at,
            "first_admin_replied_at": ticket.first_admin_replied_at,
            "last_message": ticket.last_message_text or "",
            "last_message_at": ticket.last_message_created_at or ticket.updated_at,
            "has_admin_reply": bool(ticket.has_admin_reply),
            "messages": [],
        }

    @staticmethod
    def sync_support_user(*, actor: SupportActor) -> SupportUser:
        now = timezone.now()
        defaults = {
            "username": actor.username,
            "first_name": actor.first_name,
            "last_name": actor.last_name,
            "first_seen_at": now,
            "last_seen_at": now,
        }
        support_user, created = SupportUser.objects.get_or_create(
            telegram_user_id=actor.telegram_id,
            defaults=defaults,
        )
        if created:
            return support_user

        update_fields = ["updated_at", "last_seen_at"]
        support_user.last_seen_at = now
        for field_name, value in (
            ("username", actor.username),
            ("first_name", actor.first_name),
            ("last_name", actor.last_name),
        ):
            value = (value or "").strip()
            if getattr(support_user, field_name) != value:
                setattr(support_user, field_name, value)
                update_fields.append(field_name)
        support_user.save(update_fields=update_fields)
        return support_user

    @staticmethod
    def _active_ticket_for_user(support_user: SupportUser) -> SupportTicket | None:
        return (
            SupportTicket.objects.filter(support_user=support_user)
            .exclude(status=SupportTicket.Status.CLOSED)
            .order_by("-updated_at", "-id")
            .first()
        )

    @staticmethod
    @transaction.atomic
    def receive_user_message(*, actor: SupportActor, text: str) -> tuple[SupportTicket, SupportMessage, bool]:
        clean_text = SupportService._clean_text(text)
        if not clean_text:
            raise ValidationError("Пустое сообщение нельзя отправить.")

        support_user = SupportService.sync_support_user(actor=actor)
        if support_user.is_blocked:
            raise ValidationError("Недоступно.")

        ticket = SupportService._active_ticket_for_user(support_user)
        created_ticket = False
        if ticket is None:
            ticket = SupportTicket.objects.create(
                support_user=support_user,
                telegram_user_id=support_user.telegram_user_id,
                username=support_user.username,
                first_name=support_user.first_name,
                last_name=support_user.last_name,
                status=SupportTicket.Status.NEW,
            )
            created_ticket = True
        else:
            ticket.username = support_user.username
            ticket.first_name = support_user.first_name
            ticket.last_name = support_user.last_name
            update_fields = ["updated_at", "username", "first_name", "last_name"]
            if ticket.status == SupportTicket.Status.ANSWERED:
                ticket.status = SupportTicket.Status.IN_PROGRESS if ticket.assigned_admin_id else SupportTicket.Status.NEW
                update_fields.append("status")
            ticket.save(update_fields=update_fields)

        message = SupportMessage.objects.create(
            ticket=ticket,
            sender_type=SupportMessage.SenderType.USER,
            sender_telegram_id=actor.telegram_id,
            sender_username=actor.username,
            text=clean_text,
        )
        return ticket, message, created_ticket

    @staticmethod
    def assign_ticket(*, ticket: SupportTicket, admin: SupportActor) -> SupportTicket:
        ticket.assigned_admin_id = admin.telegram_id
        ticket.assigned_admin_username = admin.username
        ticket.status = SupportTicket.Status.IN_PROGRESS
        ticket.save(update_fields=["assigned_admin_id", "assigned_admin_username", "status", "updated_at"])
        return ticket

    @staticmethod
    @transaction.atomic
    def send_admin_reply(*, ticket: SupportTicket, admin: SupportActor, text: str) -> SupportMessage:
        clean_text = SupportService._clean_text(text)
        if not clean_text:
            raise ValidationError("Введите сообщение для пользователя.")
        if ticket.status == SupportTicket.Status.CLOSED:
            raise ValidationError("Обращение уже закрыто.")

        SupportService.assign_ticket(ticket=ticket, admin=admin)
        message = SupportMessage.objects.create(
            ticket=ticket,
            sender_type=SupportMessage.SenderType.ADMIN,
            sender_telegram_id=admin.telegram_id,
            sender_username=admin.username,
            text=clean_text,
        )
        ticket.status = SupportTicket.Status.ANSWERED
        if ticket.first_admin_replied_at is None:
            ticket.first_admin_replied_at = message.created_at
            ticket.save(update_fields=["status", "first_admin_replied_at", "updated_at"])
        else:
            ticket.save(update_fields=["status", "updated_at"])
        return message

    @staticmethod
    def close_ticket(*, ticket: SupportTicket, admin: SupportActor) -> SupportTicket:
        if ticket.status == SupportTicket.Status.CLOSED:
            return ticket
        if admin.telegram_id and ticket.assigned_admin_id is None:
            ticket.assigned_admin_id = admin.telegram_id
            ticket.assigned_admin_username = admin.username
        ticket.status = SupportTicket.Status.CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(
            update_fields=[
                "assigned_admin_id",
                "assigned_admin_username",
                "status",
                "closed_at",
                "updated_at",
            ]
        )
        return ticket

    @staticmethod
    def toggle_user_block(*, support_user: SupportUser) -> SupportUser:
        support_user.is_blocked = not support_user.is_blocked
        support_user.save(update_fields=["is_blocked", "updated_at"])
        return support_user

    @staticmethod
    def get_ticket(*, ticket_id: int) -> SupportTicket:
        return (
            SupportTicket.objects.select_related("support_user")
            .prefetch_related("messages")
            .get(pk=ticket_id)
        )

    @staticmethod
    def get_ticket_snapshot(*, ticket_id: int) -> dict:
        ticket = SupportService.get_ticket(ticket_id=ticket_id)
        return SupportService._serialize_ticket(ticket)

    @staticmethod
    def list_tickets(*, scope: str, page: int = 1) -> dict:
        last_message_queryset = SupportMessage.objects.filter(ticket_id=OuterRef("pk")).order_by("-created_at", "-id")
        queryset = (
            SupportTicket.objects.select_related("support_user")
            .annotate(
                last_message_text=Subquery(last_message_queryset.values("text")[:1]),
                last_message_created_at=Subquery(last_message_queryset.values("created_at")[:1]),
                has_admin_reply=Exists(
                    SupportMessage.objects.filter(
                        ticket_id=OuterRef("pk"),
                        sender_type=SupportMessage.SenderType.ADMIN,
                    )
                ),
            )
            .order_by("-updated_at", "-id")
        )

        if scope == "new":
            queryset = queryset.filter(status=SupportTicket.Status.NEW)
        elif scope == "active":
            queryset = queryset.filter(status__in=[SupportTicket.Status.IN_PROGRESS, SupportTicket.Status.ANSWERED])
        elif scope == "closed":
            queryset = queryset.filter(status=SupportTicket.Status.CLOSED)

        total = queryset.count()
        page = max(1, page)
        start = (page - 1) * SupportService.LIST_PAGE_SIZE
        end = start + SupportService.LIST_PAGE_SIZE
        tickets = list(queryset[start:end])

        return {
            "items": [SupportService._serialize_ticket_summary(ticket) for ticket in tickets],
            "page": page,
            "has_prev": page > 1,
            "has_next": end < total,
            "total": total,
            "scope": scope,
        }

    @staticmethod
    def get_user_profile(*, support_user_id: int) -> dict:
        support_user = SupportUser.objects.get(pk=support_user_id)
        tickets = list(support_user.tickets.all())
        last_message = (
            SupportMessage.objects.filter(ticket__support_user=support_user)
            .order_by("-created_at", "-id")
            .first()
        )
        return {
            "support_user_id": support_user.id,
            "telegram_user_id": support_user.telegram_user_id,
            "username": support_user.username,
            "first_name": support_user.first_name,
            "last_name": support_user.last_name,
            "display_name": SupportService._display_name(
                first_name=support_user.first_name,
                last_name=support_user.last_name,
                username=support_user.username,
                fallback=str(support_user.telegram_user_id),
            ),
            "is_blocked": support_user.is_blocked,
            "first_seen_at": support_user.first_seen_at,
            "last_seen_at": support_user.last_seen_at,
            "tickets_total": len(tickets),
            "open_tickets_total": sum(ticket.status != SupportTicket.Status.CLOSED for ticket in tickets),
            "closed_tickets_total": sum(ticket.status == SupportTicket.Status.CLOSED for ticket in tickets),
            "last_message": last_message.text if last_message else "",
        }

    @staticmethod
    def toggle_user_block_by_id(*, support_user_id: int) -> dict:
        support_user = SupportService.toggle_user_block(support_user=SupportUser.objects.get(pk=support_user_id))
        return SupportService.get_user_profile(support_user_id=support_user.id)

    @staticmethod
    def get_analytics() -> dict:
        today = timezone.localdate()
        tickets = SupportTicket.objects.all()
        created_today = tickets.filter(created_at__date=today).count()
        answered_today = tickets.filter(first_admin_replied_at__date=today).count()
        closed_today = tickets.filter(closed_at__date=today).count()

        answered_with_timing = tickets.exclude(first_admin_replied_at__isnull=True)
        response_times = [
            (ticket.first_admin_replied_at - ticket.created_at).total_seconds()
            for ticket in answered_with_timing
            if ticket.first_admin_replied_at and ticket.created_at
        ]
        average_seconds = int(mean(response_times)) if response_times else 0

        top_users = [
            {
                "support_user_id": user.id,
                "display_name": SupportService._display_name(
                    first_name=user.first_name,
                    last_name=user.last_name,
                    username=user.username,
                    fallback=str(user.telegram_user_id),
                ),
                "username": user.username,
                "tickets_total": user.tickets_count,
            }
            for user in SupportUser.objects.annotate(tickets_count=Count("tickets"))
            .filter(tickets_count__gt=0)
            .order_by("-tickets_count", "-last_seen_at")[:5]
        ]

        return {
            "today": {
                "new": created_today,
                "answered": answered_today,
                "closed": closed_today,
            },
            "totals": {
                "all": tickets.count(),
                "open": tickets.exclude(status=SupportTicket.Status.CLOSED).count(),
                "in_progress": tickets.filter(status=SupportTicket.Status.IN_PROGRESS).count(),
                "answered": tickets.filter(status=SupportTicket.Status.ANSWERED).count(),
                "closed": tickets.filter(status=SupportTicket.Status.CLOSED).count(),
            },
            "average_response_seconds": average_seconds,
            "top_users": top_users,
        }

    @staticmethod
    def format_duration(seconds: int) -> str:
        if seconds <= 0:
            return "—"
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours} ч {minutes} мин"
        if minutes:
            return f"{minutes} мин {seconds} сек"
        return f"{seconds} сек"
