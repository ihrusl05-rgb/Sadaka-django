from django.db import models
from common.mixins.models import SoftDeleteModel
from common.utils.slugs import generate_unique_slug


class ContentItem(SoftDeleteModel):
    class Scope(models.TextChoices):
        PLATFORM = "platform", "Платформа"
        MOSQUE = "mosque", "Мечеть"

    class Type(models.TextChoices):
        NEWS = "news", "Новость"
        PAGE = "page", "Страница"
        ANNOUNCEMENT = "announcement", "Объявление"

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "На модерации"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонен"

    mosque = models.ForeignKey(
        "mosques.Mosque",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="content",
        verbose_name="Мечеть",
    )
    author = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Автор")
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Слаг")
    body = models.TextField(verbose_name="Содержимое")
    type = models.CharField(max_length=32, choices=Type.choices, verbose_name="Тип контента")
    scope = models.CharField(max_length=32, choices=Scope.choices, default=Scope.PLATFORM, verbose_name="Область")
    moderation_status = models.CharField(
        max_length=32,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        verbose_name="Статус модерации",
    )
    is_published = models.BooleanField(default=False, verbose_name="Опубликован")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата публикации")
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")

    class Meta:
        verbose_name = "элемент контента"
        verbose_name_plural = "элементы контента"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(source_value=self.title, model=type(self), instance=self)
        super().save(*args, **kwargs)
