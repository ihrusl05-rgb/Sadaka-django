from django.db import models

from common.mixins.models import TimeStampedModel


class SupportUser(TimeStampedModel):
    telegram_user_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="Telegram user ID")
    username = models.CharField(max_length=255, blank=True, verbose_name="Username")
    first_name = models.CharField(max_length=255, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, verbose_name="Фамилия")
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")
    first_seen_at = models.DateTimeField(verbose_name="Первое обращение")
    last_seen_at = models.DateTimeField(verbose_name="Последняя активность")

    class Meta:
        ordering = ["-last_seen_at", "-id"]
        verbose_name = "пользователь поддержки"
        verbose_name_plural = "пользователи поддержки"

    def __str__(self):
        parts = [self.first_name, self.last_name]
        full_name = " ".join(part for part in parts if part).strip()
        if self.username and full_name:
            return f"{full_name} (@{self.username})"
        if self.username:
            return f"@{self.username}"
        return full_name or str(self.telegram_user_id)


class SupportTicket(TimeStampedModel):
    class Status(models.TextChoices):
        NEW = "new", "🆕 Новое"
        IN_PROGRESS = "in_progress", "🟡 В работе"
        ANSWERED = "answered", "✅ Отвечено"
        CLOSED = "closed", "🔒 Закрыто"

    support_user = models.ForeignKey(
        "support.SupportUser",
        on_delete=models.CASCADE,
        related_name="tickets",
        verbose_name="Пользователь поддержки",
    )
    telegram_user_id = models.BigIntegerField(db_index=True, verbose_name="Telegram user ID")
    username = models.CharField(max_length=255, blank=True, verbose_name="Username")
    first_name = models.CharField(max_length=255, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=255, blank=True, verbose_name="Фамилия")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NEW, db_index=True, verbose_name="Статус")
    assigned_admin_id = models.BigIntegerField(null=True, blank=True, db_index=True, verbose_name="Telegram ID администратора")
    assigned_admin_username = models.CharField(max_length=255, blank=True, verbose_name="Username администратора")
    first_admin_replied_at = models.DateTimeField(null=True, blank=True, verbose_name="Первый ответ администратора")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата закрытия")

    class Meta:
        ordering = ["-updated_at", "-id"]
        verbose_name = "обращение поддержки"
        verbose_name_plural = "обращения поддержки"

    def __str__(self):
        return f"#{self.pk} {self.get_status_display()}"


class SupportMessage(TimeStampedModel):
    class SenderType(models.TextChoices):
        USER = "user", "Пользователь"
        ADMIN = "admin", "Администратор"
        SYSTEM = "system", "Система"

    ticket = models.ForeignKey(
        "support.SupportTicket",
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Обращение",
    )
    sender_type = models.CharField(max_length=16, choices=SenderType.choices, db_index=True, verbose_name="Тип отправителя")
    sender_telegram_id = models.BigIntegerField(null=True, blank=True, verbose_name="Telegram ID отправителя")
    sender_username = models.CharField(max_length=255, blank=True, verbose_name="Username отправителя")
    text = models.TextField(verbose_name="Текст")

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "сообщение поддержки"
        verbose_name_plural = "сообщения поддержки"

    def __str__(self):
        return f"{self.get_sender_type_display()}: {self.text[:40]}"

