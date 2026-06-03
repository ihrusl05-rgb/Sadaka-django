import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, TemplateView, View

from apps.platform.selectors import get_profile_page_context
from apps.platform.views import REFERRAL_SESSION_KEY
from apps.users.forms import EmailLoginForm, ProfileForm, ProfilePasswordForm, ProfileSetPasswordForm, TelegramCodeVerifyForm
from apps.users.models import User
from apps.users.max_auth import MaxAuthService
from apps.users.services import UserService
from apps.users.telegram_auth import TelegramAuthService

logger = logging.getLogger(__name__)


def _start_web_session(*, request, user) -> None:
    login(request, user)
    request.session.cycle_key()
    request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 43200))


class TelegramLoginView(TemplateView):
    template_name = "landing/telegram_login.html"
    session_token_key = "telegram_login_token"
    session_next_key = "telegram_login_next"
    session_auto_open_key = "telegram_login_auto_open"
    session_provider_key = "social_login_provider"

    SOCIAL_AUTH_CONFIG = {
        "telegram": {
            "service": TelegramAuthService,
            "start_action": "start_telegram",
            "button_label": "Войти через Telegram",
            "start_error": "TELEGRAM_AUTH_BOT_USERNAME не настроен. Вход через Telegram временно недоступен.",
            "pending_title": "Откройте Telegram-бота",
            "pending_text": "Нажмите /start в боте. Код придет в чат, а это окно автоматически переключится на ввод кода.",
            "open_label": "Открыть Telegram",
            "pending_status": "Ожидаем подтверждение в Telegram…",
            "confirmed_without_name": "Telegram подтвержден. Код уже в чате с ботом.",
            "confirmed_with_name": "Аккаунт {display_name} подтвержден. Код уже в чате с ботом.",
            "code_title": "Введите код из Telegram",
            "guide_step_1": "Нажмите кнопку входа и перейдите в auth-бот Sadaka.",
            "guide_step_2": "Бот подтвердит ваш Telegram и отправит одноразовый код.",
            "guide_note": "Безопасный вход с привязкой Telegram-аккаунта и автоматической выдачей сессии.",
            "icon_class": "has-icon icon-telegram",
        },
        "max": {
            "service": MaxAuthService,
            "start_action": "start_max",
            "button_label": "Войти через MAX",
            "start_error": "MAX_AUTH_BOT_USERNAME не настроен. Вход через MAX временно недоступен.",
            "pending_title": "Откройте MAX-бота",
            "pending_text": "Откройте чат с ботом по кнопке ниже. После подтверждения код придет в MAX, а страница переключится на ввод.",
            "open_label": "Открыть MAX",
            "pending_status": "Ожидаем подтверждение в MAX…",
            "confirmed_without_name": "MAX подтвержден. Код уже в чате с ботом.",
            "confirmed_with_name": "Аккаунт {display_name} подтвержден. Код уже в чате с ботом.",
            "code_title": "Введите код из MAX",
            "guide_step_1": "Нажмите кнопку входа и откройте auth-бот Sadaka в MAX.",
            "guide_step_2": "Бот подтвердит ваш MAX и отправит одноразовый код.",
            "guide_note": "Безопасный вход через MAX с отдельным одноразовым кодом и автоматической выдачей сессии.",
            "icon_class": "",
        },
    }

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self) -> str:
        next_url = self.request.session.get(self.session_next_key) or self.request.GET.get("next") or self.request.POST.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return next_url
        return reverse("platform:profile")

    def _clear_login_state(self) -> None:
        self.request.session.pop(self.session_token_key, None)
        self.request.session.pop(self.session_next_key, None)
        self.request.session.pop(self.session_auto_open_key, None)
        self.request.session.pop(self.session_provider_key, None)

    def get_session_token(self) -> str:
        return self.request.session.get(self.session_token_key, "")

    def get_auto_open_telegram(self) -> bool:
        if not hasattr(self, "_auto_open_telegram"):
            self._auto_open_telegram = bool(self.request.session.pop(self.session_auto_open_key, False))
        return self._auto_open_telegram

    def get_active_provider(self) -> str:
        provider = (self.request.session.get(self.session_provider_key) or "").strip().lower()
        if provider in self.SOCIAL_AUTH_CONFIG:
            return provider
        return "telegram"

    def get_provider_config(self, provider: str | None = None) -> dict:
        return self.SOCIAL_AUTH_CONFIG[provider or self.get_active_provider()]

    def _is_ajax(self, request) -> bool:
        return request.headers.get("X-Requested-With") == "XMLHttpRequest"

    def _bind_referrer(self, user) -> None:
        inviter_id = self.request.session.get(REFERRAL_SESSION_KEY)
        if not inviter_id:
            return
        inviter = User.objects.filter(pk=inviter_id).first()
        if inviter:
            UserService.bind_inviter(user=user, inviter=inviter)

    def get_login_status(self):
        token = self.get_session_token()
        if not token:
            return None
        try:
            return self.get_provider_config()["service"].get_login_status(token=token)
        except ValidationError:
            self.request.session.pop(self.session_token_key, None)
            return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        next_url = self.request.GET.get("next") or self.request.session.get(self.session_next_key) or reverse("platform:profile")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            self.request.session[self.session_next_key] = next_url
        else:
            next_url = reverse("platform:profile")

        login_status = self.get_login_status()
        social_token = self.get_session_token()
        provider = self.get_active_provider()
        provider_config = self.get_provider_config(provider)
        provider_url = ""
        if login_status:
            provider_url = getattr(login_status, "telegram_url", "") or getattr(login_status, "max_url", "")
        active_step = kwargs.get("active_step")
        if not active_step:
            if not social_token:
                active_step = "start"
            elif login_status and login_status.status == "confirmed":
                active_step = "enter_code"
            elif login_status and login_status.status == "pending":
                active_step = "await_provider"
            else:
                active_step = "start"

        context["verify_form"] = kwargs.get("verify_form", TelegramCodeVerifyForm())
        context["next_url"] = next_url
        context["auth_error"] = kwargs.get("auth_error", "")
        context["active_step"] = active_step
        context["auth_provider"] = provider
        context["auth_provider_label"] = provider_config["button_label"]
        context["provider_url"] = provider_url
        context["provider_status_url"] = (
            reverse(f"auth-{provider}-login-status", kwargs={"token": social_token}) if social_token else ""
        )
        context["provider_display_name"] = login_status.display_name if login_status else ""
        context["provider_pending_title"] = provider_config["pending_title"]
        context["provider_pending_text"] = provider_config["pending_text"]
        context["provider_pending_status"] = provider_config["pending_status"]
        context["provider_open_label"] = provider_config["open_label"]
        context["provider_code_title"] = provider_config["code_title"]
        context["provider_confirmed_without_name"] = provider_config["confirmed_without_name"]
        context["provider_confirmed_with_name"] = provider_config["confirmed_with_name"]
        context["provider_icon_class"] = provider_config["icon_class"]
        context["debug_otp_code"] = login_status.debug_code if login_status else ""
        context["auto_open_telegram"] = kwargs.get("auto_open_telegram", self.get_auto_open_telegram())
        context["email_login_form"] = kwargs.get("email_login_form", EmailLoginForm())
        context["telegram_available"] = bool(getattr(settings, "TELEGRAM_AUTH_BOT_USERNAME", "").strip())
        context["max_available"] = bool(getattr(settings, "MAX_AUTH_BOT_USERNAME", "").strip())
        context["guide_step_telegram"] = self.SOCIAL_AUTH_CONFIG["telegram"]["guide_step_1"]
        context["guide_step_telegram_confirm"] = self.SOCIAL_AUTH_CONFIG["telegram"]["guide_step_2"]
        context["guide_note_telegram"] = self.SOCIAL_AUTH_CONFIG["telegram"]["guide_note"]
        context["guide_step_max"] = self.SOCIAL_AUTH_CONFIG["max"]["guide_step_1"]
        context["guide_step_max_confirm"] = self.SOCIAL_AUTH_CONFIG["max"]["guide_step_2"]
        context["guide_note_max"] = self.SOCIAL_AUTH_CONFIG["max"]["guide_note"]
        return context

    def _issue_code(self, *, verify_form: TelegramCodeVerifyForm):
        token = self.get_session_token()
        if not token:
            return self.render_to_response(
                self.get_context_data(
                    verify_form=verify_form,
                    active_step="start",
                    auth_error="Сессия входа истекла. Начните заново.",
                )
            )
        try:
            result = self.get_provider_config()["service"].issue_code(
                token=token,
                request_ip=self.request.META.get("REMOTE_ADDR"),
                user_agent=self.request.META.get("HTTP_USER_AGENT"),
            )
        except ValidationError as exc:
            error_message = getattr(exc, "message", "") or "; ".join(exc.messages) or "Не удалось отправить код."
            if not hasattr(verify_form, "cleaned_data"):
                verify_form.full_clean()
            verify_form.add_error("code", error_message)
            return self.render_to_response(
                self.get_context_data(
                    verify_form=verify_form,
                    active_step="enter_code",
                )
            )
        if result.debug_code:
            self.request.session.modified = True
        return HttpResponseRedirect(self.request.path)

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")
        next_url = request.POST.get("next") or reverse("platform:profile")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            request.session[self.session_next_key] = next_url

        if action in {"start_telegram", "start_max"}:
            provider = "telegram" if action == "start_telegram" else "max"
            provider_config = self.get_provider_config(provider)
            try:
                result = provider_config["service"].create_login_token(
                    request_ip=request.META.get("REMOTE_ADDR"),
                    user_agent=request.META.get("HTTP_USER_AGENT"),
                )
            except ValidationError as exc:
                if self._is_ajax(request):
                    return JsonResponse({"ok": False, "error": exc.message}, status=400)
                return self.render_to_response(self.get_context_data(auth_error=exc.message))
            provider_url = getattr(result, "telegram_url", "") or getattr(result, "max_url", "")
            if not provider_url:
                error_message = provider_config["start_error"]
                if self._is_ajax(request):
                    return JsonResponse({"ok": False, "error": error_message}, status=400)
                return self.render_to_response(self.get_context_data(auth_error=error_message))
            request.session[self.session_token_key] = result.login_token.token
            request.session[self.session_provider_key] = provider
            if self._is_ajax(request):
                request.session[self.session_auto_open_key] = False
            else:
                request.session[self.session_auto_open_key] = True
            logger.info("%s login started", provider, extra={"login_token": result.login_token.token[:8]})
            if self._is_ajax(request):
                payload = {
                    "ok": True,
                    "auth_url": provider_url,
                    "redirect_url": reverse("platform:login"),
                }
                if provider == "telegram":
                    payload["telegram_url"] = provider_url
                elif provider == "max":
                    payload["max_url"] = provider_url
                return JsonResponse(payload)
            return redirect("platform:login")

        if action == "request_code":
            verify_form = TelegramCodeVerifyForm()
            return self._issue_code(verify_form=verify_form)

        if action == "reset_login":
            self._clear_login_state()
            return redirect("platform:login")

        if action == "verify_code":
            verify_form = TelegramCodeVerifyForm(request.POST)
            token = self.get_session_token()
            if not token:
                verify_form.add_error("code", "Сессия входа истекла. Начните заново.")
            elif verify_form.is_valid():
                try:
                    user, _ = self.get_provider_config()["service"].verify_code(
                        token=token,
                        code=verify_form.cleaned_data["code"],
                    )
                except ValidationError as exc:
                    verify_form.add_error("code", exc.message)
                else:
                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    _start_web_session(request=request, user=user)
                    self._bind_referrer(user)
                    self._clear_login_state()
                    return redirect(next_url)
            return self.render_to_response(self.get_context_data(verify_form=verify_form, active_step="enter_code"))

        if action == "email_login":
            email_login_form = EmailLoginForm(request.POST)
            if email_login_form.is_valid():
                try:
                    user, _ = UserService.login(**email_login_form.cleaned_data)
                except ValidationError as exc:
                    email_login_form.add_error(None, exc.message)
                else:
                    user.backend = "django.contrib.auth.backends.ModelBackend"
                    _start_web_session(request=request, user=user)
                    self._bind_referrer(user)
                    self._clear_login_state()
                    return redirect(next_url)
            return self.render_to_response(self.get_context_data(email_login_form=email_login_form, active_step="start"))

        return redirect("platform:login")


class LogoutView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        next_url = request.POST.get("next") or reverse("platform:landing")
        if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = reverse("platform:landing")
        logout(request)
        return redirect(next_url)


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = "landing/profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Личный кабинет"
        context["current_page"] = "profile"
        context["profile_section"] = "overview"
        context.update(get_profile_page_context(user=self.request.user, request=self.request))
        return context


class ProfileHistoryView(LoginRequiredMixin, TemplateView):
    template_name = "landing/profile_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "История помощи"
        context["current_page"] = "profile"
        context["profile_section"] = "history"
        context.update(get_profile_page_context(user=self.request.user, request=self.request))
        return context


class ProfileSubscriptionsView(LoginRequiredMixin, TemplateView):
    template_name = "landing/profile_subscriptions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Подписки"
        context["current_page"] = "profile"
        context["profile_section"] = "subscriptions"
        context.update(get_profile_page_context(user=self.request.user, request=self.request))
        return context


class ProfileSettingsView(LoginRequiredMixin, TemplateView):
    template_name = "landing/profile_settings.html"

    def get_success_url(self):
        return reverse("platform:profile-settings")

    def get_profile_form(self):
        return ProfileForm(instance=self.request.user)

    def get_password_form(self):
        if self.request.user.has_usable_password():
            return ProfilePasswordForm()
        return ProfileSetPasswordForm()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Настройки профиля"
        context["current_page"] = "profile"
        context["profile_section"] = "settings"
        context["profile_form"] = kwargs.get("profile_form", self.get_profile_form())
        context["password_form"] = kwargs.get("password_form", self.get_password_form())
        context["profile_has_usable_password"] = self.request.user.has_usable_password()
        context.update(get_profile_page_context(user=self.request.user, request=self.request))
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action") or "profile"
        profile_form = ProfileForm(request.POST, instance=request.user)
        password_form = self.get_password_form()

        if action == "password":
            password_form = ProfilePasswordForm(request.POST) if request.user.has_usable_password() else ProfileSetPasswordForm(request.POST)
            profile_form = self.get_profile_form()
            if password_form.is_valid():
                if request.user.has_usable_password():
                    try:
                        UserService.change_password(
                            user=request.user,
                            current_password=password_form.cleaned_data["current_password"],
                            new_password=password_form.cleaned_data["new_password"],
                        )
                    except ValidationError as exc:
                        password_form.add_error("current_password", exc.message)
                    else:
                        messages.success(request, "Пароль обновлён.")
                        return redirect(self.get_success_url())
                else:
                    UserService.set_password(
                        user=request.user,
                        new_password=password_form.cleaned_data["new_password"],
                    )
                    messages.success(request, "Пароль установлен.")
                    return redirect(self.get_success_url())
        else:
            password_form = self.get_password_form()
            if profile_form.is_valid():
                UserService.update_profile(user=request.user, **profile_form.cleaned_data)
                messages.success(request, "Данные профиля сохранены.")
                return redirect(self.get_success_url())

        return self.render_to_response(
            self.get_context_data(
                profile_form=profile_form,
                password_form=password_form,
            )
        )


class ProfileTelegramConnectView(LoginRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            result = TelegramAuthService.create_login_token(
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT"),
                user=request.user,
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
            return redirect("platform:profile-settings")

        if not result.telegram_url:
            messages.error(request, "TELEGRAM_AUTH_BOT_USERNAME не настроен. Привязка Telegram временно недоступна.")
            return redirect("platform:profile-settings")

        return HttpResponseRedirect(result.telegram_url)
