from django.db import models
from common.mixins.models import SoftDeleteModel
from common.utils.slugs import generate_unique_slug


class Project(SoftDeleteModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PENDING = "pending", "На модерации"
        APPROVED = "approved", "Одобрен"
        REJECTED = "rejected", "Отклонен"
        ACTIVE = "active", "Активен"
        COMPLETED = "completed", "Завершен"
        ARCHIVED = "archived", "В архиве"

    mosque = models.ForeignKey("mosques.Mosque", on_delete=models.CASCADE, related_name="projects", verbose_name="Мечеть")
    created_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Создал пользователь",
    )
    title = models.CharField(max_length=255, verbose_name="Название проекта")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Слаг")
    cover_image = models.ImageField(upload_to="projects/covers/", null=True, blank=True, verbose_name="Обложка")
    description = models.TextField(verbose_name="Описание проекта")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT, verbose_name="Статус")
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Целевая сумма")
    current_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Собранная сумма")
    start_date = models.DateField(null=True, blank=True, verbose_name="Дата начала")
    end_date = models.DateField(null=True, blank=True, verbose_name="Дата окончания")
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата публикации")
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирован")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "проект"
        verbose_name_plural = "проекты"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(source_value=self.title, model=type(self), instance=self)
        super().save(*args, **kwargs)

    @property
    def progress(self):
        if not self.goal_amount:
            return 0
        return round((self.current_amount / self.goal_amount) * 100, 2)
