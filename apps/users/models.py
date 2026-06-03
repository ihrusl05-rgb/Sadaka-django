from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from common.mixins.models import SoftDeleteModel, TimeStampedModel


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email field must be set.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.USER)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.PLATFORM_ADMIN)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, SoftDeleteModel):
    PHONE_AUTH_EMAIL_DOMAIN = "phone-auth.sadaka.local"
    TELEGRAM_AUTH_EMAIL_DOMAIN = "telegram-auth.sadaka.local"
    MAX_AUTH_EMAIL_DOMAIN = "max-auth.sadaka.local"

    class Role(models.TextChoices):
        USER = "user", "Пользователь"
        MOSQUE_ADMIN = "mosque_admin", "Администратор мечети"
        PLATFORM_ADMIN = "platform_admin", "Администратор платформы"

    email = models.EmailField(unique=True, verbose_name="Email")
    full_name = models.CharField(max_length=255, blank=True, verbose_name="Полное имя")
    first_name = models.CharField(max_length=150, blank=True, verbose_name="Имя")
    last_name = models.CharField(max_length=150, blank=True, verbose_name="Фамилия")
    middle_name = models.CharField(max_length=150, blank=True, verbose_name="Отчество")
    phone = models.CharField(max_length=32, blank=True, verbose_name="Телефон")
    photo = models.ImageField(upload_to="users/photos/", null=True, blank=True, verbose_name="Фото")
    invited_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invited_users",
        verbose_name="Пригласивший пользователь",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.USER, verbose_name="Роль")
    is_staff = models.BooleanField(default=False, verbose_name="Доступ в админку")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_email_verified = models.BooleanField(default=False, verbose_name="Email подтвержден")
    is_phone_verified = models.BooleanField(default=False, verbose_name="Телефон подтвержден")
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")
    blocked_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата блокировки")
    last_activity_at = models.DateTimeField(null=True, blank=True, verbose_name="Последняя активность")
    date_joined = models.DateTimeField(default=timezone.now, verbose_name="Дата регистрации")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["-date_joined"]
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self):
        return self.email

    @staticmethod
    def split_full_name(value: str) -> tuple[str, str, str]:
        parts = [part for part in (value or "").split() if part]
        if not parts:
            return ("", "", "")
        if len(parts) == 1:
            return ("", parts[0], "")
        if len(parts) == 2:
            return (parts[0], parts[1], "")
        return (parts[0], parts[1], " ".join(parts[2:]))

    @staticmethod
    def build_full_name(*, last_name: str = "", first_name: str = "", middle_name: str = "") -> str:
        return " ".join(part for part in [last_name.strip(), first_name.strip(), middle_name.strip()] if part).strip()

    @classmethod
    def is_phone_auth_email(cls, email: str) -> bool:
        normalized = (email or "").strip().lower()
        return normalized.startswith("phone_") and normalized.endswith(f"@{cls.PHONE_AUTH_EMAIL_DOMAIN}")

    @classmethod
    def is_telegram_auth_email(cls, email: str) -> bool:
        normalized = (email or "").strip().lower()
        return normalized.startswith("telegram_") and normalized.endswith(f"@{cls.TELEGRAM_AUTH_EMAIL_DOMAIN}")

    @classmethod
    def is_max_auth_email(cls, email: str) -> bool:
        normalized = (email or "").strip().lower()
        return normalized.startswith("max_") and normalized.endswith(f"@{cls.MAX_AUTH_EMAIL_DOMAIN}")

    @classmethod
    def is_placeholder_email(cls, email: str) -> bool:
        return cls.is_phone_auth_email(email) or cls.is_telegram_auth_email(email) or cls.is_max_auth_email(email)

    @property
    def profile_email(self) -> str:
        return "" if self.is_placeholder_email(self.email) else self.email

    def save(self, *args, **kwargs):
        self.first_name = (self.first_name or "").strip()
        self.last_name = (self.last_name or "").strip()
        self.middle_name = (self.middle_name or "").strip()
        self.full_name = (self.full_name or "").strip()

        if self.first_name or self.last_name or self.middle_name:
            self.full_name = self.build_full_name(
                last_name=self.last_name,
                first_name=self.first_name,
                middle_name=self.middle_name,
            )
        elif self.full_name:
            self.last_name, self.first_name, self.middle_name = self.split_full_name(self.full_name)

        self.email = self.__class__.objects.normalize_email(self.email)
        if not self.is_superuser:
            self.is_staff = self.role in {self.Role.MOSQUE_ADMIN, self.Role.PLATFORM_ADMIN}
        super().save(*args, **kwargs)

    @property
    def is_platform_admin(self) -> bool:
        return self.role == self.Role.PLATFORM_ADMIN or self.is_superuser

    @property
    def is_mosque_admin(self) -> bool:
        return self.role == self.Role.MOSQUE_ADMIN

    @property
    def managed_mosques(self):
        from apps.mosques.models import Mosque

        return Mosque.objects.filter(memberships__user=self)


class TelegramAccount(TimeStampedModel):
    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="telegram_account",
        verbose_name="Пользователь",
    )
    telegram_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="Telegram ID")
    chat_id = models.BigIntegerField(blank=True, null=True, verbose_name="Telegram chat ID")
    username = models.CharField(max_length=255, blank=True, verbose_name="Telegram username")
    first_name = models.CharField(max_length=255, blank=True, verbose_name="Имя в Telegram")
    last_name = models.CharField(max_length=255, blank=True, verbose_name="Фамилия в Telegram")
    photo_url = models.URLField(blank=True, verbose_name="Фото профиля Telegram")
    auth_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата подтверждения Telegram")
    linked_at = models.DateTimeField(default=timezone.now, verbose_name="Дата привязки")

    class Meta:
        ordering = ["-linked_at"]
        verbose_name = "Telegram-аккаунт"
        verbose_name_plural = "Telegram-аккаунты"

    def __str__(self):
        username = f"@{self.username}" if self.username else str(self.telegram_id)
        return username


class TelegramLoginToken(TimeStampedModel):
    token = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Токен входа")
    user = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="telegram_login_tokens",
        verbose_name="Пользователь",
    )
    telegram_account = models.ForeignKey(
        "users.TelegramAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="login_tokens",
        verbose_name="Telegram-аккаунт",
    )
    expires_at = models.DateTimeField(db_index=True, verbose_name="Срок действия")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Подтвержден в Telegram")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершен")
    code_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Код отправлен")
    requested_by_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="User-Agent")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Telegram login token"
        verbose_name_plural = "Telegram login tokens"

    def __str__(self):
        return self.token

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


class TelegramAuthCode(TimeStampedModel):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="telegram_auth_codes",
        verbose_name="Пользователь",
    )
    telegram_account = models.ForeignKey(
        "users.TelegramAccount",
        on_delete=models.CASCADE,
        related_name="auth_codes",
        verbose_name="Telegram-аккаунт",
    )
    login_token = models.ForeignKey(
        "users.TelegramLoginToken",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="auth_codes",
        verbose_name="Токен входа",
    )
    telegram_id = models.BigIntegerField(db_index=True, verbose_name="Telegram ID")
    code_hash = models.CharField(max_length=128, verbose_name="Хэш кода")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Срок действия")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Попыток ввода")
    max_attempts = models.PositiveSmallIntegerField(default=5, verbose_name="Лимит попыток")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="Использован")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="User-Agent")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Telegram-код входа"
        verbose_name_plural = "Telegram-коды входа"

    def __str__(self):
        return f"{self.telegram_id} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None


class MaxAccount(TimeStampedModel):
    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="max_account",
        verbose_name="Пользователь",
    )
    max_user_id = models.BigIntegerField(unique=True, db_index=True, verbose_name="MAX user ID")
    chat_id = models.BigIntegerField(blank=True, null=True, verbose_name="MAX chat ID")
    username = models.CharField(max_length=255, blank=True, verbose_name="MAX username")
    first_name = models.CharField(max_length=255, blank=True, verbose_name="Имя в MAX")
    last_name = models.CharField(max_length=255, blank=True, verbose_name="Фамилия в MAX")
    photo_url = models.URLField(blank=True, verbose_name="Фото профиля MAX")
    auth_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата подтверждения MAX")
    linked_at = models.DateTimeField(default=timezone.now, verbose_name="Дата привязки")

    class Meta:
        ordering = ["-linked_at"]
        verbose_name = "MAX-аккаунт"
        verbose_name_plural = "MAX-аккаунты"

    def __str__(self):
        username = f"@{self.username}" if self.username else str(self.max_user_id)
        return username


class MaxLoginToken(TimeStampedModel):
    token = models.CharField(max_length=64, unique=True, db_index=True, verbose_name="Токен входа")
    user = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="max_login_tokens",
        verbose_name="Пользователь",
    )
    max_account = models.ForeignKey(
        "users.MaxAccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="login_tokens",
        verbose_name="MAX-аккаунт",
    )
    expires_at = models.DateTimeField(db_index=True, verbose_name="Срок действия")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Подтвержден в MAX")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Завершен")
    code_sent_at = models.DateTimeField(null=True, blank=True, verbose_name="Код отправлен")
    requested_by_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="User-Agent")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MAX login token"
        verbose_name_plural = "MAX login tokens"

    def __str__(self):
        return self.token

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


class MaxAuthCode(TimeStampedModel):
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="max_auth_codes",
        verbose_name="Пользователь",
    )
    max_account = models.ForeignKey(
        "users.MaxAccount",
        on_delete=models.CASCADE,
        related_name="auth_codes",
        verbose_name="MAX-аккаунт",
    )
    login_token = models.ForeignKey(
        "users.MaxLoginToken",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="auth_codes",
        verbose_name="Токен входа",
    )
    max_user_id = models.BigIntegerField(db_index=True, verbose_name="MAX user ID")
    code_hash = models.CharField(max_length=128, verbose_name="Хэш кода")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Срок действия")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Попыток ввода")
    max_attempts = models.PositiveSmallIntegerField(default=5, verbose_name="Лимит попыток")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="Использован")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP-адрес")
    user_agent = models.CharField(max_length=255, blank=True, verbose_name="User-Agent")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "MAX-код входа"
        verbose_name_plural = "MAX-коды входа"

    def __str__(self):
        return f"{self.max_user_id} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
