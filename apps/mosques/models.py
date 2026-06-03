from django.core.exceptions import ValidationError
from django.db import models
from common.mixins.models import SoftDeleteModel, TimeStampedModel
from common.utils.slugs import generate_unique_slug


class Mosque(SoftDeleteModel):
    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "На проверке"
        VERIFIED = "verified", "Подтверждена"
        REJECTED = "rejected", "Отклонена"

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "На модерации"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"

    name = models.CharField(max_length=255, verbose_name="Имя мечети")
    slug = models.SlugField(max_length=255, unique=True, verbose_name="Слаг")
    description = models.TextField(verbose_name="Описание мечети")
    public_story = models.TextField(blank=True, verbose_name="Публичная история")
    city = models.CharField(max_length=128, verbose_name="Город")
    address = models.CharField(max_length=255, verbose_name="Адрес")
    contact_email = models.EmailField(verbose_name="Email для связи")
    contact_phone = models.CharField(max_length=32, verbose_name="Телефон для связи")
    cover_image = models.ImageField(upload_to="mosques/covers/", null=True, blank=True, verbose_name="Обложка")
    featured_project = models.ForeignKey(
        "projects.Project",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="featured_in_mosques",
        verbose_name="Главный публичный проект",
    )
    legal_name = models.CharField(max_length=255, blank=True, verbose_name="Юридическое наименование")
    inn = models.CharField(max_length=32, blank=True, verbose_name="ИНН")
    kpp = models.CharField(max_length=32, blank=True, verbose_name="КПП")
    ogrn = models.CharField(max_length=32, blank=True, verbose_name="ОГРН")
    bank_account = models.CharField(max_length=64, blank=True, verbose_name="Расчетный счет")
    bank_name = models.CharField(max_length=255, blank=True, verbose_name="Банк")
    bik = models.CharField(max_length=32, blank=True, verbose_name="БИК")
    corr_account = models.CharField(max_length=64, blank=True, verbose_name="Корр. счет")
    legal_address = models.CharField(max_length=255, blank=True, verbose_name="Юридический адрес")
    actual_address = models.CharField(max_length=255, blank=True, verbose_name="Фактический адрес")
    okpo = models.CharField(max_length=32, blank=True, verbose_name="ОКПО")
    oktmo = models.CharField(max_length=32, blank=True, verbose_name="ОКТМО")
    okato = models.CharField(max_length=32, blank=True, verbose_name="ОКАТО")
    verification_status = models.CharField(
        max_length=32,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        verbose_name="Статус верификации",
    )
    moderation_status = models.CharField(
        max_length=32,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
        verbose_name="Статус модерации",
    )
    is_blocked = models.BooleanField(default=False, verbose_name="Заблокирована")
    blocked_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата блокировки")
    blocked_reason = models.CharField(max_length=255, blank=True, verbose_name="Причина блокировки")
    commission_override = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Индивидуальная комиссия (%)",
    )
    published_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата публикации")
    created_by = models.ForeignKey(
        "users.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_mosques",
        verbose_name="Создал пользователь",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "мечеть"
        verbose_name_plural = "мечети"

    def __str__(self):
        return self.name

    def clean(self):
        if self.featured_project_id and self.featured_project.mosque_id != self.id:
            raise ValidationError({"featured_project": "Главный проект должен относиться к выбранной мечети."})

    def save(self, *args, **kwargs):
        self.slug = generate_unique_slug(source_value=self.name, model=type(self), instance=self)
        super().save(*args, **kwargs)


class MosqueMembership(TimeStampedModel):
    mosque = models.ForeignKey(Mosque, on_delete=models.CASCADE, related_name="memberships", verbose_name="Мечеть")
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="mosque_memberships",
        verbose_name="Пользователь",
    )
    is_primary = models.BooleanField(default=False, verbose_name="Основной администратор")

    class Meta:
        unique_together = ("mosque", "user")
        ordering = ["-is_primary", "id"]
        verbose_name = "связь администратора с мечетью"
        verbose_name_plural = "связи администраторов с мечетями"

    def __str__(self):
        return f"{self.user.email} -> {self.mosque.name}"


class MosqueGalleryImage(TimeStampedModel):
    mosque = models.ForeignKey(Mosque, on_delete=models.CASCADE, related_name="gallery_images", verbose_name="Мечеть")
    image = models.ImageField(upload_to="mosques/gallery/", verbose_name="Изображение")
    caption = models.CharField(max_length=255, blank=True, verbose_name="Подпись")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "фотография мечети"
        verbose_name_plural = "фотографии мечети"

    def __str__(self):
        return self.caption or f"Фото #{self.pk}"


class MosqueExpenseItem(TimeStampedModel):
    mosque = models.ForeignKey(Mosque, on_delete=models.CASCADE, related_name="expense_items", verbose_name="Мечеть")
    title = models.CharField(max_length=255, verbose_name="Статья расхода")
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Сумма")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "статья расходов"
        verbose_name_plural = "статьи расходов"

    def __str__(self):
        return self.title


class MosqueDocument(TimeStampedModel):
    mosque = models.ForeignKey(Mosque, on_delete=models.CASCADE, related_name="documents", verbose_name="Мечеть")
    title = models.CharField(max_length=255, verbose_name="Название")
    file = models.FileField(upload_to="mosques/documents/", verbose_name="Файл")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "документ мечети"
        verbose_name_plural = "документы мечети"

    def __str__(self):
        return self.title


class MosquePartner(TimeStampedModel):
    mosque = models.ForeignKey(Mosque, on_delete=models.CASCADE, related_name="partners", verbose_name="Мечеть")
    name = models.CharField(max_length=255, verbose_name="Название")
    website_url = models.URLField(blank=True, verbose_name="Сайт")
    logo = models.ImageField(upload_to="mosques/partners/", null=True, blank=True, verbose_name="Логотип")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "партнер мечети"
        verbose_name_plural = "партнеры мечети"

    def __str__(self):
        return self.name
