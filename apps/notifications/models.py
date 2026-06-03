from django.db import models

from common.mixins.models import SoftDeleteModel


class Notification(SoftDeleteModel):
    class NotificationType(models.TextChoices):
        INFO = "info", "Информация"
        SUCCESS = "success", "Успех"
        WARNING = "warning", "Предупреждение"
        ERROR = "error", "Ошибка"

    class Event(models.TextChoices):
        DONATION_SUCCESS = "donation_success", "Успешное пожертвование"
        DONATION_FAILED = "donation_failed", "Ошибка пожертвования"
        RECURRING_PAYMENT_SUCCESS = "recurring_payment_success", "Успешный регулярный платеж"
        RECURRING_PAYMENT_FAILED = "recurring_payment_failed", "Ошибка регулярного платежа"
        RECURRING_PAYMENT_REMINDER = "recurring_payment_reminder", "Напоминание о регулярном платеже"
        PROJECT_COMPLETED = "project_completed", "Проект завершен"
        PROFILE_UPDATED = "profile_updated", "Профиль обновлен"
        PASSWORD_CHANGED = "password_changed", "Пароль изменен"
        SUPPORT_REPLY = "support_reply", "Ответ поддержки"
        COMPLAINT_REPLY = "complaint_reply", "Ответ по жалобе"
        MOSQUE_DONATION_RECEIVED = "mosque_donation_received", "Поступило пожертвование мечети"
        MOSQUE_PROJECT_CREATED = "mosque_project_created", "Создан проект мечети"
        MOSQUE_PROJECT_APPROVED = "mosque_project_approved", "Проект мечети одобрен"
        MOSQUE_PROJECT_REJECTED = "mosque_project_rejected", "Проект мечети отклонен"
        MOSQUE_COMPLAINT_CREATED = "mosque_complaint_created", "Поступила жалоба"
        MOSQUE_CONTENT_APPROVED = "mosque_content_approved", "Контент мечети одобрен"
        MOSQUE_CONTENT_REJECTED = "mosque_content_rejected", "Контент мечети отклонен"
        MOSQUE_REPORT_READY = "mosque_report_ready", "Отчет мечети готов"
        MOSQUE_REQUEST_CREATED = "mosque_request_created", "Новая заявка на мечеть"
        MOSQUE_REQUEST_SUBMITTED = "mosque_request_submitted", "Заявка на мечеть отправлена"
        MOSQUE_REQUEST_APPROVED = "mosque_request_approved", "Заявка на мечеть одобрена"
        MOSQUE_REQUEST_REJECTED = "mosque_request_rejected", "Заявка на мечеть отклонена"
        MOSQUE_SUBMITTED = "mosque_submitted", "Мечеть отправлена на модерацию"
        MOSQUE_APPROVED = "mosque_approved", "Мечеть одобрена"
        MOSQUE_REJECTED = "mosque_rejected", "Мечеть отклонена"
        PROJECT_SUBMITTED = "project_submitted", "Проект отправлен на модерацию"
        PROJECT_APPROVED = "project_approved", "Проект одобрен"
        PROJECT_REJECTED = "project_rejected", "Проект отклонен"
        PROJECT_NEEDS_CHANGES = "project_needs_changes", "Проект требует исправлений"
        PROJECT_PUBLISHED = "project_published", "Проект опубликован"
        COMPLAINT_CREATED = "complaint_created", "Создана жалоба"
        PAYMENT_ERROR = "payment_error", "Ошибка оплаты"
        SYSTEM_ERROR = "system_error", "Системная ошибка"
        SUSPICIOUS_ACTIVITY = "suspicious_activity", "Подозрительная активность"
        NEW_USER_REGISTERED = "new_user_registered", "Новый пользователь"
        TEST = "test", "Тестовое уведомление"

    user = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="notifications",
        verbose_name="Пользователь",
    )
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")
    notification_type = models.CharField(
        max_length=16,
        choices=NotificationType.choices,
        default=NotificationType.INFO,
        db_index=True,
        verbose_name="Тип уведомления",
    )
    event = models.CharField(max_length=64, blank=True, db_index=True, verbose_name="Событие")
    link = models.CharField(max_length=500, blank=True, verbose_name="Ссылка")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Прочитано")
    is_sound_enabled = models.BooleanField(default=True, verbose_name="Звук включен")
    sound_key = models.CharField(max_length=64, default="default", verbose_name="Ключ звука")
    payload = models.JSONField(default=dict, blank=True, verbose_name="Служебные данные")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата прочтения")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "уведомление"
        verbose_name_plural = "уведомления"
        indexes = [
            models.Index(fields=["user", "is_read"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["event"]),
            models.Index(fields=["notification_type"]),
        ]

    def __str__(self):
        user_label = self.user.email if self.user_id and self.user else "system"
        return f"{self.title} -> {user_label}"
