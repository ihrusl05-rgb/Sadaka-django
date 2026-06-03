import logging
import json
import re

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, TemplateView, View

from apps.donations.models import Donation
from apps.donations.services import DonationService
from apps.mosques.selectors import get_public_mosque_queryset
from apps.platform.namaz import NamazServiceError, get_namaz_payload, reverse_location, search_locations
from apps.platform.forms import AddMosqueRequestForm, AddMosqueWidgetForm, GuestSubscriptionForm, PublicMosqueSupportForm
from apps.notifications.models import Notification
from apps.notifications.services import NotificationService
from apps.platform.selectors import get_landing_page_context, get_public_mosque_detail_context
from apps.platform.services import MosqueSiteRequestService
from apps.projects.models import Project
from apps.support.notifications import (
    SupportNotificationError,
    send_add_mosque_request_notification,
    send_mosque_widget_request_notification,
)
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import SubscriptionService
from apps.users.models import User

logger = logging.getLogger(__name__)
REFERRAL_SESSION_KEY = "platform_referrer_user_id"


HELP_FAQ_CATEGORIES = [
    {"slug": "all", "label": "Все"},
    {"slug": "popular", "label": "Популярные"},
    {"slug": "donations", "label": "Пожертвования"},
    {"slug": "projects", "label": "Проекты"},
    {"slug": "other", "label": "Другое"},
]

HELP_FAQ_ITEMS = [
    {
        "question": "Как найти нужную мечеть?",
        "answer": "Используйте поиск по названию, городу или адресу, чтобы быстро найти мечеть и перейти к её проектам и сборам.",
        "categories": ["popular", "other"],
    },
    {
        "question": "Можно ли совершить садака без регистрации?",
        "answer": "Да, платформа поддерживает быстрые пожертвования без обязательной регистрации аккаунта.",
        "categories": ["popular", "donations"],
    },
    {
        "question": "Чем отличается помощь мечети от помощи проекту?",
        "answer": "Помощь мечети направляется на общие нужды и развитие мечети, а помощь проекту — на конкретную инициативу: строительство, ремонт, обучение, воду и другие благие дела.",
        "categories": ["projects"],
    },
    {
        "question": "Как работает регулярная садака?",
        "answer": "Вы можете оформить ежемесячную поддержку, и пожертвование будет автоматически отправляться выбранной мечети или проекту.",
        "categories": ["popular", "donations"],
    },
    {
        "question": "Где посмотреть отчетность и прозрачность сборов?",
        "answer": "На страницах мечетей и проектов отображаются сборы, активность, обновления и публичная информация о пожертвованиях.",
        "categories": ["projects", "other"],
    },
    {
        "question": "Что делать, если моей мечети нет на платформе?",
        "answer": "Вы можете отправить заявку на добавление мечети, и команда платформы рассмотрит её после проверки информации.",
        "categories": ["other"],
    },
]


def _get_actor(request):
    return request.user if getattr(request.user, "is_authenticated", False) else None


def _store_referral_in_session(request) -> None:
    raw_ref = (request.GET.get("ref") or "").strip()
    if not raw_ref:
        return
    match = re.fullmatch(r"user-(\d+)", raw_ref)
    if not match:
        request.session.pop(REFERRAL_SESSION_KEY, None)
        return
    inviter_id = int(match.group(1))
    if not User.objects.filter(pk=inviter_id).exists():
        request.session.pop(REFERRAL_SESSION_KEY, None)
        return
    request.session[REFERRAL_SESSION_KEY] = inviter_id
    request.session.modified = True


def _get_profile_initial(request) -> dict:
    actor = _get_actor(request)
    if actor is None:
        return {}
    full_name = (
        actor.full_name
        or actor.build_full_name(
            last_name=actor.last_name,
            first_name=actor.first_name,
            middle_name=actor.middle_name,
        )
    ).strip()
    return {
        "full_name": full_name,
        "email": actor.profile_email,
    }


def _get_project_initial(request, *, mosque) -> str:
    raw_value = (request.GET.get("project") or "").strip()
    if not raw_value.isdigit():
        return ""
    return raw_value if mosque.projects.filter(pk=raw_value, status=Project.Status.ACTIVE, is_blocked=False).exists() else ""


def _build_support_targets(*, active_projects: list[dict], selected_value: str) -> list[dict]:
    targets = [
        {
            "value": "",
            "title": "В мечеть в целом",
            "description": "Поддержка общего фонда мечети и срочных нужд без привязки к одному сбору.",
            "current_amount": None,
            "goal_amount": None,
            "progress_percent": None,
            "selected": selected_value == "",
            "featured": False,
        }
    ]
    for project in active_projects:
        targets.append(
            {
                "value": str(project["id"]),
                "title": project["title"],
                "description": project["description"],
                "current_amount": project["current_amount"],
                "goal_amount": project["goal_amount"],
                "progress_percent": project["progress_percent"],
                "selected": selected_value == str(project["id"]),
                "featured": project["is_featured"],
            }
        )
    return targets


class PublicPageMixin:
    current_page = "landing"

    def dispatch(self, request, *args, **kwargs):
        _store_referral_in_session(request)
        return super().dispatch(request, *args, **kwargs)

    def get_page_context(self) -> dict:
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_page"] = self.current_page
        context.update(self.get_page_context())
        return context


class LandingPageView(PublicPageMixin, TemplateView):
    template_name = "landing/index.html"

    def get_page_context(self) -> dict:
        return get_landing_page_context()


class MosquesCatalogView(PublicPageMixin, TemplateView):
    template_name = "landing/mosques_catalog.html"
    current_page = "mosques"

    def get_page_context(self) -> dict:
        context = get_landing_page_context()
        return context


class HelpPageView(PublicPageMixin, FormView):
    template_name = "landing/help.html"
    current_page = "help"
    form_class = AddMosqueRequestForm
    success_url = reverse_lazy("platform:help")

    def get_page_context(self) -> dict:
        context = get_landing_page_context()
        context["page_title"] = "Помощь и ответы"
        context["faq_categories"] = HELP_FAQ_CATEGORIES
        context["faq_items"] = [
            {
                **item,
                "categories_value": " ".join(item["categories"]),
            }
            for item in HELP_FAQ_ITEMS
        ]
        return context

    def form_valid(self, form):
        payload = {
            "full_name": form.cleaned_data["full_name"],
            "mosque_name": form.cleaned_data["mosque_name"],
            "region": form.cleaned_data["region"],
            "phone": form.cleaned_data["phone"],
        }
        site_request = MosqueSiteRequestService.create_help_request(**payload)
        try:
            send_add_mosque_request_notification(request_snapshot=MosqueSiteRequestService.serialize(site_request))
        except SupportNotificationError:
            logger.exception("Unable to deliver add mosque request to support bot admins", extra={"request_id": site_request.id, **payload})

        NotificationService.notify_platform_admins(
            title="Новая заявка на добавление мечети",
            message=f"Поступила заявка от {payload['full_name']} на добавление мечети «{payload['mosque_name']}» ({payload['region']}).",
            event=Notification.Event.MOSQUE_REQUEST_CREATED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/platform_core/mosquesiterequest/",
            payload={"request_id": site_request.id, **payload},
        )
        logger.info("Mosque add request submitted", extra=payload)
        messages.success(self.request, "Заявка отправлена. Мы перезвоним в течение 24 часов после проверки данных.")
        return super().form_valid(form)


class AboutPageView(PublicPageMixin, TemplateView):
    template_name = "landing/about.html"
    current_page = "about"

    def get_page_context(self) -> dict:
        context = get_landing_page_context()
        context["page_title"] = "О нас"
        return context


class MosqueWidgetRequestView(View):
    http_method_names = ["post"]

    @staticmethod
    def _get_form_payload(request) -> dict:
        content_type = (request.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type == "application/json":
            try:
                payload = json.loads(request.body.decode("utf-8") or "{}")
            except (TypeError, ValueError, UnicodeDecodeError):
                return {}
            return payload if isinstance(payload, dict) else {}
        return request.POST

    def post(self, request, *args, **kwargs):
        form = AddMosqueWidgetForm(self._get_form_payload(request))
        if not form.is_valid():
            return JsonResponse(
                {
                    "success": False,
                    "message": "Проверьте обязательные поля формы.",
                    "errors": form.errors.get_json_data(escape_html=True),
                },
                status=400,
            )

        payload = {
            "mosque_name": form.cleaned_data["mosque_name"],
            "city": form.cleaned_data["city"],
            "applicant_name": form.cleaned_data["applicant_name"],
            "phone": form.cleaned_data["contact"],
            "comment": form.cleaned_data["comment"],
        }
        site_request = MosqueSiteRequestService.create_widget_request(**payload)
        try:
            send_mosque_widget_request_notification(request_snapshot=MosqueSiteRequestService.serialize(site_request))
        except SupportNotificationError:
            logger.exception(
                "Unable to deliver mosque widget request to Telegram admins",
                extra={
                    "request_id": site_request.id,
                    "mosque_name": payload["mosque_name"],
                    "city": payload["city"],
                    "has_applicant_name": bool(payload["applicant_name"]),
                    "has_comment": bool(payload["comment"]),
                },
            )

        NotificationService.notify_platform_admins(
            title="Новая заявка с сайта на добавление мечети",
            message=f"Поступила заявка по мечети «{payload['mosque_name']}», город: {payload['city']}.",
            event=Notification.Event.MOSQUE_REQUEST_CREATED,
            notification_type=Notification.NotificationType.INFO,
            link="/admin/platform_core/mosquesiterequest/",
            payload={"request_id": site_request.id, **payload},
        )
        return JsonResponse(
            {
                "success": True,
                "message": "Спасибо! Заявка отправлена. Мы свяжемся с вами.",
            }
        )


class NamazPageView(PublicPageMixin, TemplateView):
    template_name = "landing/namaz.html"
    current_page = "namaz"

    def get_page_context(self) -> dict:
        context = get_landing_page_context()
        context["page_title"] = "Намаз"
        return context


class NamazCitySearchView(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        query = (request.GET.get("q") or "").strip()
        if len(query) < 2:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Введите хотя бы 2 символа для поиска города.",
                    "results": [],
                },
                status=400,
            )

        try:
            results = search_locations(query=query, limit=6)
        except NamazServiceError:
            logger.exception("Unable to search namaz locations", extra={"query": query})
            return JsonResponse(
                {
                    "success": False,
                    "message": "Не удалось выполнить поиск города. Попробуйте позже.",
                    "results": [],
                },
                status=503,
            )

        return JsonResponse({"success": True, "results": results})


class NamazDataView(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        try:
            lat = float((request.GET.get("lat") or "").strip())
            lon = float((request.GET.get("lon") or "").strip())
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Укажите корректные координаты города.",
                },
                status=400,
            )

        city = (request.GET.get("city") or "").strip()
        region = (request.GET.get("region") or "").strip()
        country = (request.GET.get("country") or "").strip()
        country_code = (request.GET.get("country_code") or "").strip()

        try:
            payload = get_namaz_payload(
                lat=lat,
                lon=lon,
                city=city,
                region=region,
                country=country,
                country_code=country_code,
            )
        except NamazServiceError:
            logger.exception("Unable to load namaz data", extra={"lat": lat, "lon": lon, "city": city})
            return JsonResponse(
                {
                    "success": False,
                    "message": "Не удалось загрузить время намаза. Попробуйте позже.",
                },
                status=503,
            )

        return JsonResponse({"success": True, **payload})


class NamazLocateView(View):
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        try:
            lat = float((request.GET.get("lat") or "").strip())
            lon = float((request.GET.get("lon") or "").strip())
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Укажите корректные координаты для определения города.",
                },
                status=400,
            )

        try:
            location = reverse_location(lat=lat, lon=lon)
        except NamazServiceError:
            logger.exception("Unable to resolve namaz location", extra={"lat": lat, "lon": lon})
            return JsonResponse(
                {
                    "success": False,
                    "message": "Не удалось определить город по координатам. Попробуйте выбрать его вручную.",
                },
                status=503,
            )

        return JsonResponse({"success": True, "location": location})


class PublicMosqueDetailView(FormView):
    template_name = "landing/mosque_detail.html"
    form_class = PublicMosqueSupportForm

    def get_mosque(self):
        if not hasattr(self, "_mosque"):
            queryset = (
                get_public_mosque_queryset()
                .prefetch_related("gallery_images", "expense_items", "documents", "partners", "projects")
            )
            self._mosque = get_object_or_404(queryset, slug=self.kwargs["slug"])
        return self._mosque

    def get_detail_context(self):
        if not hasattr(self, "_detail_context"):
            self._detail_context = get_public_mosque_detail_context(mosque=self.get_mosque())
        return self._detail_context

    def get_initial(self):
        initial = super().get_initial()
        initial["mode"] = self.request.GET.get("mode") if self.request.GET.get("mode") in {"once", "monthly"} else "once"
        initial["amount"] = self.request.GET.get("amount") or "1000"
        initial["payment_method"] = self.request.GET.get("payment_method") or Donation.PaymentMethod.CARD
        initial["project"] = _get_project_initial(self.request, mosque=self.get_mosque())
        initial.update(_get_profile_initial(self.request))
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = _get_actor(self.request)
        kwargs["mosque"] = self.get_mosque()
        return kwargs

    def form_valid(self, form):
        mosque = self.get_mosque()
        project = form.cleaned_data["project"]
        actor = _get_actor(self.request)
        payload = {
            "actor": actor,
            "mosque": mosque,
            "project": project,
            "amount": form.cleaned_data["amount"],
            "payment_method": form.cleaned_data["payment_method"],
            "guest_full_name": form.cleaned_data["full_name"],
            "guest_email": form.cleaned_data["email"],
            "is_public_anonymous": form.cleaned_data["is_public_anonymous"],
            "metadata": {
                "public_checkout": True,
                "public_mosque_page": True,
                "mode": form.cleaned_data["mode"],
            },
        }

        if form.cleaned_data["mode"] == PublicMosqueSupportForm.MODE_MONTHLY:
            subscription = SubscriptionService.create_subscription(
                interval=Subscription.Interval.MONTHLY,
                **payload,
            )
            messages.success(
                self.request,
                f"Ежемесячная поддержка подключена. Номер подписки: {subscription.provider_subscription_id}.",
            )
        else:
            donation = DonationService.create_donation(**payload)
            donation = DonationService.confirm_payment(donation=donation, actor=actor)
            messages.success(self.request, f"Пожертвование успешно оформлено. Квитанция: {donation.receipt_number}.")

        return redirect(
            f"{reverse('platform:public-mosque-detail', kwargs={'slug': mosque.slug})}"
            f"?mode={form.cleaned_data['mode']}&amount={form.cleaned_data['amount']}"
            f"{f'&project={project.id}' if project else ''}"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_detail_context())
        context["current_page"] = "mosques"
        context["page_title"] = self.get_mosque().name
        context["support_form"] = context["form"]
        context["open_support_modal"] = self.request.GET.get("support") == "1" or bool(context["form"].errors)
        context["selected_mode"] = context["form"].initial.get("mode", PublicMosqueSupportForm.MODE_ONCE)
        selected_project_value = str(context["form"]["project"].value() or "")
        context["selected_support_project_value"] = selected_project_value
        context["support_targets"] = _build_support_targets(
            active_projects=context["active_projects"],
            selected_value=selected_project_value,
        )
        return context


class GuestDonationView(FormView):
    def get_redirect_url(self):
        target = reverse("platform:guest-subscription")
        params = self.request.GET.urlencode()
        return f"{target}?{params}" if params else target

    def get(self, request, *args, **kwargs):
        return redirect(self.get_redirect_url())

    def post(self, request, *args, **kwargs):
        return redirect(self.get_redirect_url())


class GuestSubscriptionView(FormView):
    template_name = "landing/guest_checkout.html"
    form_class = GuestSubscriptionForm
    success_url = reverse_lazy("platform:guest-subscription")

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("mosque"):
            initial["mosque"] = self.request.GET["mosque"]
        if self.request.GET.get("amount"):
            initial["amount"] = self.request.GET["amount"]
        initial.update(_get_profile_initial(self.request))
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = _get_actor(self.request)
        return kwargs

    def form_valid(self, form):
        actor = _get_actor(self.request)
        subscription = SubscriptionService.create_subscription(
            actor=actor,
            mosque=form.cleaned_data["mosque"],
            amount=form.cleaned_data["amount"],
            interval=Subscription.Interval.MONTHLY,
            payment_method=Donation.PaymentMethod.MOCK,
            guest_full_name=form.cleaned_data["full_name"],
            guest_email=form.cleaned_data["email"],
            metadata={"public_checkout": True},
        )
        messages.success(self.request, f"Ежемесячная поддержка подключена. Номер подписки: {subscription.provider_subscription_id}.")
        return redirect(f"{reverse('platform:guest-subscription')}?mosque={subscription.mosque_id}&amount={subscription.amount}")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Ежемесячная поддержка"
        context["submit_label"] = "Оформить подписку"
        context["mode"] = "monthly"
        return context
