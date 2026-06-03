from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.users.models import User


class TelegramCodeVerifyForm(forms.Form):
    code = forms.CharField(
        label="Код из Telegram",
        max_length=6,
        min_length=6,
        widget=forms.HiddenInput(attrs={"data-otp-value": "true"}),
    )

    def clean_code(self):
        code = "".join(ch for ch in self.cleaned_data["code"] if ch.isdigit())
        if len(code) != 6:
            raise forms.ValidationError("Введите 6-значный код.")
        return code


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", "placeholder": "Введите пароль"}),
    )


class ProfileForm(forms.ModelForm):
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False, max_length=32)

    class Meta:
        model = User
        fields = ("last_name", "first_name", "middle_name", "phone", "email")
        widgets = {
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "middle_name": forms.TextInput(attrs={"autocomplete": "additional-name"}),
            "phone": forms.TextInput(attrs={"autocomplete": "tel", "inputmode": "tel"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = self.instance.profile_email
        self.fields["phone"].initial = self.instance.phone


class ProfilePasswordForm(forms.Form):
    current_password = forms.CharField(
        label="Текущий пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    new_password = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        validators=[validate_password],
    )
    new_password_confirm = forms.CharField(
        label="Повторите новый пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")
        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error("new_password_confirm", "Пароли не совпадают.")
        return cleaned_data


class ProfileSetPasswordForm(forms.Form):
    new_password = forms.CharField(
        label="Новый пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        validators=[validate_password],
    )
    new_password_confirm = forms.CharField(
        label="Повторите новый пароль",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")
        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error("new_password_confirm", "Пароли не совпадают.")
        return cleaned_data
