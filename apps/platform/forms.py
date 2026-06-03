from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError as DjangoValidationError

from apps.donations.models import Donation
from apps.mosques.models import Mosque
from apps.mosques.selectors import get_public_mosque_queryset
from apps.projects.models import Project
from apps.users.services import UserService


def _normalize_site_phone(value: str) -> str:
    compact_value = " ".join((value or "").split()).strip()
    digits = "".join(symbol for symbol in compact_value if symbol.isdigit())
    if not digits:
        raise forms.ValidationError("Укажите номер телефона в формате +7XXXXXXXXXX.")
    if len(digits) != 11 or digits[0] not in {"7", "8"}:
        raise forms.ValidationError("Укажите номер телефона в формате +7XXXXXXXXXX.")
    try:
        return UserService.normalize_phone(compact_value)
    except DjangoValidationError as exc:
        raise forms.ValidationError(exc.message)


class GuestDonationBaseForm(forms.Form):
    mosque = forms.ModelChoiceField(
        queryset=Mosque.objects.none(),
        label="Мечеть",
        empty_label=None,
    )
    amount = forms.DecimalField(
        label="Сумма",
        min_value=Decimal("1.00"),
        max_digits=12,
        decimal_places=2,
    )
    full_name = forms.CharField(label="Имя и фамилия", max_length=255, required=False)
    email = forms.EmailField(label="Email", required=False)

    def __init__(self, *args, **kwargs):
        self.actor = kwargs.pop("actor", None)
        super().__init__(*args, **kwargs)
        self.fields["mosque"].queryset = get_public_mosque_queryset().order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        full_name = (cleaned_data.get("full_name") or "").strip()
        email = (cleaned_data.get("email") or "").strip().lower()

        if not getattr(self.actor, "is_authenticated", False) and not full_name:
            self.add_error("full_name", "Укажите имя и фамилию.")

        cleaned_data["full_name"] = full_name
        cleaned_data["email"] = email
        return cleaned_data


class GuestDonationForm(GuestDonationBaseForm):
    pass


class GuestSubscriptionForm(GuestDonationBaseForm):
    pass


class AddMosqueRequestForm(forms.Form):
    full_name = forms.CharField(label="ФИО", max_length=255)
    mosque_name = forms.CharField(label="Название мечети", max_length=255)
    region = forms.CharField(label="Регион", max_length=255)
    phone = forms.CharField(label="Номер телефона", max_length=32)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["full_name"].widget.attrs.update(
            {
                "placeholder": "Имя и фамилия",
                "autocomplete": "name",
            }
        )
        self.fields["mosque_name"].widget.attrs.update(
            {
                "placeholder": "Например, Соборная мечеть",
                "autocomplete": "organization",
            }
        )
        self.fields["region"].widget.attrs.update(
            {
                "placeholder": "Город или регион",
                "autocomplete": "address-level1",
                "list": "mosque-region-options",
            }
        )
        self.fields["phone"].widget.attrs.update(
            {
                "placeholder": "+7 (900) 000-00-00",
                "autocomplete": "tel",
                "inputmode": "tel",
                "pattern": r"^\+?[78][\d\s\-\(\)]{10,}$",
            }
        )

    def clean_full_name(self):
        return " ".join((self.cleaned_data["full_name"] or "").split()).strip()

    def clean_mosque_name(self):
        return " ".join((self.cleaned_data["mosque_name"] or "").split()).strip()

    def clean_region(self):
        return " ".join((self.cleaned_data["region"] or "").split()).strip()

    def clean_phone(self):
        return _normalize_site_phone(self.cleaned_data["phone"])


class AddMosqueWidgetForm(forms.Form):
    mosque_name = forms.CharField(label="Название мечети", max_length=255)
    city = forms.CharField(label="Город / населенный пункт", max_length=255)
    applicant_name = forms.CharField(label="Имя заявителя", max_length=255, required=False)
    contact = forms.CharField(label="Телефон для связи", max_length=32)
    comment = forms.CharField(label="Комментарий", max_length=2000, required=False, widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["mosque_name"].widget.attrs.update(
            {
                "placeholder": "Например, Соборная мечеть",
                "autocomplete": "organization",
                "maxlength": 255,
            }
        )
        self.fields["city"].widget.attrs.update(
            {
                "placeholder": "Город или населенный пункт",
                "autocomplete": "address-level2",
                "maxlength": 255,
            }
        )
        self.fields["applicant_name"].widget.attrs.update(
            {
                "placeholder": "Как к вам обращаться",
                "autocomplete": "name",
                "maxlength": 255,
            }
        )
        self.fields["contact"].widget.attrs.update(
            {
                "placeholder": "+7 (900) 000-00-00",
                "autocomplete": "tel",
                "inputmode": "tel",
                "maxlength": 32,
                "pattern": r"^\+?[78][\d\s\-\(\)]{10,}$",
            }
        )
        self.fields["comment"].widget.attrs.update(
            {
                "placeholder": "Дополнительная информация о мечети или заявке",
                "rows": 4,
                "maxlength": 2000,
            }
        )

        for field_name in ("mosque_name", "city", "contact"):
            self.fields[field_name].widget.attrs["required"] = "required"

    def _clean_compact_text(self, field_name: str) -> str:
        return " ".join((self.cleaned_data.get(field_name) or "").split()).strip()

    def clean_mosque_name(self):
        return self._clean_compact_text("mosque_name")

    def clean_city(self):
        return self._clean_compact_text("city")

    def clean_applicant_name(self):
        return self._clean_compact_text("applicant_name")

    def clean_contact(self):
        return _normalize_site_phone(self._clean_compact_text("contact"))

    def clean_comment(self):
        return (self.cleaned_data.get("comment") or "").strip()


class PublicMosqueSupportForm(forms.Form):
    MODE_ONCE = "once"
    MODE_MONTHLY = "monthly"
    MODE_CHOICES = (
        (MODE_ONCE, "Разово"),
        (MODE_MONTHLY, "Ежемесячно"),
    )

    PAYMENT_CHOICES = (
        (Donation.PaymentMethod.CARD, "Банковской картой"),
        (Donation.PaymentMethod.SBP, "Через СБП"),
    )

    mode = forms.ChoiceField(choices=MODE_CHOICES, widget=forms.HiddenInput())
    project = forms.ChoiceField(required=False)
    amount = forms.DecimalField(
        label="Сумма",
        min_value=Decimal("1.00"),
        max_digits=12,
        decimal_places=2,
    )
    payment_method = forms.ChoiceField(choices=PAYMENT_CHOICES, label="Способ оплаты", widget=forms.HiddenInput())
    full_name = forms.CharField(label="Имя и фамилия", max_length=255, required=False)
    email = forms.EmailField(label="Email", required=False)
    is_public_anonymous = forms.BooleanField(label="Анонимно", required=False)
    consent = forms.BooleanField(label="Согласие", required=True)

    def __init__(self, *args, **kwargs):
        self.actor = kwargs.pop("actor", None)
        self.mosque = kwargs.pop("mosque", None)
        super().__init__(*args, **kwargs)
        self.active_projects = list(
            Project.objects.filter(mosque=self.mosque, status=Project.Status.ACTIVE, is_blocked=False).order_by("-goal_amount", "id")
            if self.mosque
            else Project.objects.none()
        )
        self.project_map = {str(project.pk): project for project in self.active_projects}
        self.fields["project"].choices = [("", "В мечеть в целом")] + [
            (str(project.pk), project.title) for project in self.active_projects
        ]
        self.fields["amount"].widget.attrs.update(
            {
                "placeholder": "Внести свою сумму",
                "inputmode": "decimal",
                "data-amount-input": "true",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        is_public_anonymous = cleaned_data.get("is_public_anonymous")
        full_name = (cleaned_data.get("full_name") or "").strip()
        email = (cleaned_data.get("email") or "").strip().lower()
        project_value = (cleaned_data.get("project") or "").strip()

        if project_value:
            project = self.project_map.get(project_value)
            if project is None:
                self.add_error("project", "Выберите активный проект этой мечети.")
            cleaned_data["project"] = project
        else:
            cleaned_data["project"] = None

        if is_public_anonymous:
            cleaned_data["full_name"] = ""
            cleaned_data["email"] = ""
            cleaned_data["is_public_anonymous"] = True
            return cleaned_data

        if not getattr(self.actor, "is_authenticated", False) and not full_name:
            self.add_error("full_name", "Укажите имя и фамилию.")

        cleaned_data["full_name"] = full_name
        cleaned_data["email"] = email

        return cleaned_data
