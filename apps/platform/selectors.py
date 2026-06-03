from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Prefetch, Q, Sum
from django.db.models.functions import Coalesce
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from apps.donations.models import Donation
from apps.mosques.models import Mosque
from apps.mosques.selectors import get_public_mosque_queryset
from apps.notifications.models import Notification
from apps.projects.models import Project
from apps.subscriptions.models import Subscription
from apps.users.models import TelegramAccount, User


def mask_public_name(name: str, *, anonymous: bool = False, anonymous_label: str = "Анонимный спонсор") -> str:
    if anonymous:
        return anonymous_label

    clean = " ".join((name or "").split()).strip()
    if not clean:
        return "Аноним"
    parts = clean.split(" ")
    first = parts[0]
    if len(parts) > 1 and parts[1]:
        return f"{first} {parts[1][0]}."
    if "@" in first:
        local = first.split("@", 1)[0]
        return local[:1].upper() + "***"
    return first


def _donor_identity(donation: Donation) -> tuple[str, str]:
    if donation.user_id:
        label = donation.user.full_name or donation.user.email
        return (f"user:{donation.user_id}", mask_public_name(label, anonymous=donation.is_public_anonymous))
    if donation.guest_email:
        label = donation.guest_full_name or donation.guest_email
        return (f"guest:{donation.guest_email.lower()}", mask_public_name(label, anonymous=donation.is_public_anonymous))
    if donation.guest_full_name:
        return (
            f"guest-name:{donation.guest_full_name.lower()}",
            mask_public_name(donation.guest_full_name, anonymous=donation.is_public_anonymous),
        )
    return (f"anonymous:{donation.pk}", "Анонимный спонсор")


def _subscription_identity(subscription: Subscription) -> tuple[str, str]:
    if subscription.user_id:
        label = subscription.user.full_name or subscription.user.email
        return (f"user:{subscription.user_id}", mask_public_name(label, anonymous=subscription.is_public_anonymous))
    if subscription.guest_email:
        label = subscription.guest_full_name or subscription.guest_email
        return (
            f"guest:{subscription.guest_email.lower()}",
            mask_public_name(label, anonymous=subscription.is_public_anonymous, anonymous_label="Аноним"),
        )
    if subscription.guest_full_name:
        return (
            f"guest-name:{subscription.guest_full_name.lower()}",
            mask_public_name(subscription.guest_full_name, anonymous=subscription.is_public_anonymous, anonymous_label="Аноним"),
        )
    return (f"anonymous:{subscription.pk}", "Аноним")


def _build_top_users(donations: list[Donation], limit: int = 5):
    aggregated = {}
    for donation in donations:
        key, label = _donor_identity(donation)
        payload = aggregated.setdefault(
            key,
            {
                "name": label,
                "amount": Decimal("0.00"),
                "count": 0,
            },
        )
        payload["amount"] += donation.amount
        payload["count"] += 1

    by_amount = [
        dict(item)
        for item in sorted(
            aggregated.values(),
            key=lambda item: (item["amount"], item["count"], item["name"]),
            reverse=True,
        )[:limit]
    ]
    by_count = [
        dict(item)
        for item in sorted(
            aggregated.values(),
            key=lambda item: (item["count"], item["amount"], item["name"]),
            reverse=True,
        )[:limit]
    ]

    for index, item in enumerate(by_amount, start=1):
        item["rank"] = index
    for index, item in enumerate(by_count, start=1):
        item["rank"] = index
    return {"by_amount": by_amount, "by_count": by_count}


def _build_ranked_supporters(donations: list[Donation], limit: int = 10) -> list[dict]:
    aggregated = {}
    for donation in donations:
        key, label = _donor_identity(donation)
        payload = aggregated.setdefault(
            key,
            {
                "name": label,
                "amount": Decimal("0.00"),
                "count": 0,
                "occurred_at": donation.paid_at or donation.created_at,
            },
        )
        payload["amount"] += donation.amount
        payload["count"] += 1
        payload["occurred_at"] = max(payload["occurred_at"], donation.paid_at or donation.created_at)

    return [
        dict(item)
        for item in sorted(
            aggregated.values(),
            key=lambda item: (item["amount"], item["count"], item["occurred_at"]),
            reverse=True,
        )[:limit]
    ]


def _profile_public_name(user: User) -> str:
    label = (user.full_name or "").strip()
    if label:
        return mask_public_name(label, anonymous_label="Аноним")
    if user.profile_email:
        return mask_public_name(user.profile_email, anonymous_label="Аноним")
    return f"Аноним #{user.pk}"


def _build_profile_initials(user: User) -> str:
    parts = [part.strip() for part in [user.first_name, user.last_name] if part and part.strip()]
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    if len(parts) == 1:
        return parts[0][0].upper()
    full_name = (user.full_name or "").strip()
    if full_name:
        tokens = [token for token in full_name.split() if token]
        if len(tokens) >= 2:
            return f"{tokens[0][0]}{tokens[1][0]}".upper()
        if tokens:
            return tokens[0][0].upper()
    email = (user.profile_email or user.email or "S").strip()
    return email[0].upper()


def _build_referral_leaderboard(*, current_user: User, limit: int = 10) -> tuple[list[dict], dict]:
    leaderboard_queryset = (
        User.objects.filter(invited_users__isnull=False)
        .annotate(
            invited_count=Count("invited_users", distinct=True),
            referred_payments_count=Count(
                "invited_users__donations",
                filter=Q(invited_users__donations__status=Donation.Status.SUCCEEDED),
                distinct=True,
            ),
            referred_payments_total=Coalesce(
                Sum(
                    "invited_users__donations__amount",
                    filter=Q(invited_users__donations__status=Donation.Status.SUCCEEDED),
                ),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by("-invited_count", "-referred_payments_total", "date_joined", "pk")
    )

    leaderboard = []
    current_user_stats = {
        "rank": None,
        "name": _profile_public_name(current_user),
        "days_in_good": max((timezone.localdate() - current_user.date_joined.date()).days, 0),
        "invited_count": 0,
        "referred_payments_count": 0,
        "referred_payments_total": Decimal("0.00"),
        "is_current_user": True,
    }

    for rank, inviter in enumerate(leaderboard_queryset, start=1):
        row = {
            "rank": rank,
            "name": _profile_public_name(inviter),
            "days_in_good": max((timezone.localdate() - inviter.date_joined.date()).days, 0),
            "invited_count": inviter.invited_count,
            "referred_payments_count": inviter.referred_payments_count,
            "referred_payments_total": inviter.referred_payments_total,
            "is_current_user": inviter.pk == current_user.pk,
        }
        if rank <= limit:
            leaderboard.append(row)
        if inviter.pk == current_user.pk:
            current_user_stats = row

    if current_user_stats["rank"] is None:
        invited_users = User.objects.filter(invited_by=current_user)
        current_user_stats["invited_count"] = invited_users.count()
        payment_totals = Donation.objects.filter(user__invited_by=current_user, status=Donation.Status.SUCCEEDED).aggregate(
            referred_payments_count=Count("id"),
            referred_payments_total=Coalesce(
                Sum("amount"),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        current_user_stats["referred_payments_count"] = payment_totals["referred_payments_count"] or 0
        current_user_stats["referred_payments_total"] = payment_totals["referred_payments_total"] or Decimal("0.00")

    return leaderboard, current_user_stats


def _active_project_prefetch():
    return Prefetch(
        "projects",
        queryset=Project.objects.filter(status=Project.Status.ACTIVE, is_blocked=False).order_by("-goal_amount", "id"),
    )


def _annotated_public_mosques():
    return (
        get_public_mosque_queryset()
        .select_related("featured_project")
        .prefetch_related(_active_project_prefetch())
        .annotate(
            collected_total=Coalesce(
                Sum(
                    "donations__amount",
                    filter=Q(donations__status=Donation.Status.SUCCEEDED),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                Decimal("0.00"),
            ),
            successful_donations_count=Count("donations", filter=Q(donations__status=Donation.Status.SUCCEEDED), distinct=True),
        )
    )


def _file_url(field_file) -> str:
    if not field_file:
        return ""
    try:
        return field_file.url
    except ValueError:
        return ""


def _build_searchable_mosque_payload(mosque: Mosque) -> dict:
    active_projects = list(mosque.projects.all())
    goal_total = sum((project.goal_amount for project in active_projects), Decimal("0.00"))
    remaining_total = max(goal_total - mosque.collected_total, Decimal("0.00"))
    return {
        "slug": mosque.slug,
        "name": mosque.name,
        "city": mosque.city,
        "address": mosque.address,
        "description": mosque.description,
        "cover_image_url": _file_url(mosque.cover_image) or static("landing/mosque-card-fallback.png"),
        "collected_total": mosque.collected_total,
        "goal_total": goal_total,
        "remaining_total": remaining_total,
        "progress_percent": _project_progress_percent(current_amount=mosque.collected_total, goal_amount=goal_total),
        "detail_url": reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
    }


def _resolve_featured_project(*, mosque: Mosque, active_projects: list[Project]) -> Project | None:
    if mosque.featured_project_id:
        for project in active_projects:
            if project.id == mosque.featured_project_id:
                return project
    return active_projects[0] if active_projects else None


def _project_progress_percent(*, current_amount: Decimal, goal_amount: Decimal) -> int:
    if not goal_amount:
        return 0
    return int(min((current_amount / goal_amount) * 100, Decimal("100")))


def _build_public_project_payload(project: Project, *, is_featured: bool = False) -> dict:
    current_amount = project.current_amount or Decimal("0.00")
    goal_amount = project.goal_amount or Decimal("0.00")
    remaining_amount = max(goal_amount - current_amount, Decimal("0.00"))
    return {
        "id": project.id,
        "title": project.title,
        "cover_image_url": _file_url(project.cover_image),
        "description": project.description,
        "goal_amount": goal_amount,
        "current_amount": current_amount,
        "remaining_amount": remaining_amount,
        "progress_percent": _project_progress_percent(current_amount=current_amount, goal_amount=goal_amount),
        "status": project.status,
        "status_label": project.get_status_display(),
        "is_featured": is_featured,
    }


def get_landing_page_context():
    public_mosques = list(_annotated_public_mosques())

    successful_donations = list(
        Donation.objects.filter(status=Donation.Status.SUCCEEDED, mosque__in=[mosque.pk for mosque in public_mosques])
        .select_related("user", "mosque")
        .order_by("-paid_at", "-created_at")
    )

    today = timezone.localdate()
    donor_keys_today = {
        _donor_identity(donation)[0]
        for donation in successful_donations
        if donation.paid_at and timezone.localtime(donation.paid_at).date() == today
    }
    donations_today = [
        donation
        for donation in successful_donations
        if donation.paid_at and timezone.localtime(donation.paid_at).date() == today
    ]
    donated_today = sum((donation.amount for donation in donations_today), Decimal("0.00"))

    live_feed = [
        {
            "donor_name": _donor_identity(donation)[1],
            "amount": donation.amount,
            "mosque_name": donation.mosque.name,
            "paid_at": donation.paid_at or donation.created_at,
        }
        for donation in successful_donations[:6]
    ]

    searchable_mosques = [
        _build_searchable_mosque_payload(mosque)
        for mosque in sorted(public_mosques, key=lambda item: ((item.city or "").lower(), item.name.lower()))
    ]
    available_cities = sorted({mosque.city for mosque in public_mosques if mosque.city}, key=str.lower)

    total_collected = sum((donation.amount for donation in successful_donations), Decimal("0.00"))
    top_users = _build_top_users(successful_donations)

    return {
        "hero": {
            "title": "Совершай садака джария — награда, которая не прекращается",
            "hadith": "Прозрачная помощь мечетям, строительство добра и участие в делах, за которые награда продолжается даже после жизни.",
        },
        "quick_amounts": [500, 1000, 3000, 5000],
        "available_cities": available_cities,
        "searchable_mosques": searchable_mosques,
        "live_feed": live_feed,
        "top_users": top_users,
        "stats": {
            "total_collected": total_collected,
            "donors_today": len(donor_keys_today),
            "donated_today": donated_today,
            "mosques_total": len(public_mosques),
        },
    }


def get_public_mosque_detail_context(*, mosque: Mosque) -> dict:
    active_projects = list(
        mosque.projects.filter(status=Project.Status.ACTIVE, is_blocked=False).order_by("-goal_amount", "id")
    )
    featured_project = _resolve_featured_project(mosque=mosque, active_projects=active_projects)
    completed_projects = list(
        mosque.projects.filter(status__in=[Project.Status.COMPLETED, Project.Status.ARCHIVED], is_blocked=False).order_by("-updated_at", "-id")
    )

    successful_donations = list(
        Donation.objects.filter(mosque=mosque, status=Donation.Status.SUCCEEDED)
        .select_related("user", "subscription")
        .order_by("-paid_at", "-created_at")
    )
    active_subscriptions = list(
        Subscription.objects.filter(mosque=mosque, status=Subscription.Status.ACTIVE)
        .select_related("user")
        .order_by("-created_at")
    )

    collected_total = sum((donation.amount for donation in successful_donations), Decimal("0.00"))
    goal_total = sum((project.goal_amount for project in active_projects), Decimal("0.00"))
    if not goal_total:
        goal_total = collected_total or Decimal("1.00")

    remaining_total = max(goal_total - collected_total, Decimal("0.00"))
    progress_percent = int(min((collected_total / goal_total) * 100, Decimal("100"))) if goal_total else 0
    average_donation = (collected_total / len(successful_donations)).quantize(Decimal("0.01")) if successful_donations else Decimal("0.00")

    legal_info = [
        ("Наименование", mosque.legal_name),
        ("ИНН", mosque.inn),
        ("КПП", mosque.kpp),
        ("ОГРН", mosque.ogrn),
        ("Расчетный счет", mosque.bank_account),
        ("Банк", mosque.bank_name),
        ("БИК", mosque.bik),
        ("Корр. счет", mosque.corr_account),
        ("Юридический адрес", mosque.legal_address),
        ("Фактический адрес", mosque.actual_address),
        ("ОКПО", mosque.okpo),
        ("ОКТМО", mosque.oktmo),
        ("ОКАТО", mosque.okato),
    ]
    legal_info = [(label, value) for label, value in legal_info if value]

    recent_supporters = [
        {
            "name": _donor_identity(donation)[1],
            "amount": donation.amount,
            "occurred_at": donation.paid_at or donation.created_at,
        }
        for donation in successful_donations[:10]
    ]

    autopay_donations = [
        donation
        for donation in successful_donations
        if donation.subscription_id or donation.metadata.get("recurring")
    ]

    ummah_members = [
        {
            "name": _subscription_identity(subscription)[1],
            "joined_at": subscription.created_at,
        }
        for subscription in active_subscriptions[:10]
    ]

    return {
        "mosque": mosque,
        "featured_project": featured_project,
        "project": featured_project,
        "quick_amounts": [100, 500, 1000, 3000],
        "collected_total": collected_total,
        "goal_total": goal_total,
        "remaining_total": remaining_total,
        "progress_percent": progress_percent,
        "average_donation": average_donation,
        "active_projects_total": len(active_projects),
        "active_projects": [
            _build_public_project_payload(project, is_featured=bool(featured_project and project.id == featured_project.id))
            for project in active_projects
        ],
        "completed_projects": [_build_public_project_payload(project) for project in completed_projects],
        "recent_supporters": recent_supporters,
        "top_supporters": _build_ranked_supporters(successful_donations),
        "top_autopayments": _build_ranked_supporters(autopay_donations),
        "supporters_total": len(successful_donations),
        "ummah_members": ummah_members,
        "ummah_total": len(active_subscriptions),
        "gallery_images": list(mosque.gallery_images.all()),
        "expense_items": list(mosque.expense_items.all()),
        "documents": list(mosque.documents.all()),
        "partners": list(mosque.partners.all()),
        "legal_info": legal_info,
    }


def get_profile_page_context(*, user, request) -> dict:
    donations = list(
        Donation.objects.filter(user=user)
        .select_related("mosque", "project", "subscription")
        .order_by("-paid_at", "-created_at")
    )
    active_subscriptions = list(
        Subscription.objects.filter(user=user, status=Subscription.Status.ACTIVE)
        .select_related("mosque", "project")
        .order_by("-created_at")
    )
    invite_link = request.build_absolute_uri(f"{reverse('platform:landing')}?ref=user-{user.pk}")
    successful_donations = [donation for donation in donations if donation.status == Donation.Status.SUCCEEDED]
    total_donated = sum((donation.amount for donation in successful_donations), Decimal("0.00"))
    monthly_commitment = sum((subscription.amount for subscription in active_subscriptions), Decimal("0.00"))
    latest_support = successful_donations[0] if successful_donations else None

    try:
        telegram_account = user.telegram_account
    except TelegramAccount.DoesNotExist:
        telegram_account = None

    telegram_profile = None
    if telegram_account:
        telegram_profile = {
            "username": telegram_account.username,
            "display_name": f"@{telegram_account.username}" if telegram_account.username else telegram_account.first_name or "Telegram подключен",
            "linked_at": telegram_account.linked_at,
            "is_linked": True,
        }

    recent_support = [
        {
            "kind": "donation",
            "title": donation.project.title if donation.project_id else "Поддержка мечети",
            "mosque_name": donation.mosque.name,
            "amount": donation.amount,
            "status": donation.get_status_display(),
            "date": donation.paid_at or donation.created_at,
        }
        for donation in successful_donations[:4]
    ]
    recent_notifications = list(
        Notification.objects.filter(user=user)
        .order_by("-created_at")[:3]
    )
    referral_leaderboard, referral_overview = _build_referral_leaderboard(current_user=user, limit=10)
    display_name = user.full_name or user.first_name or "Ваш профиль"
    primary_contact = user.profile_email or user.phone or "Контакты пока не заполнены"
    site_meta = getattr(request, "site_meta", None)
    quick_actions = [
        {
            "title": "Помочь сейчас",
            "description": "Открыть подборку мечетей и сделать новое пожертвование.",
            "href": f"{reverse('platform:landing')}#quick-donate",
        },
        {
            "title": "Мои уведомления",
            "description": "Посмотреть свежие события по аккаунту и платежам.",
            "href": "/profile/notifications/",
        },
        {
            "title": "Настройки профиля",
            "description": "Обновить имя, контакты и параметры доступа.",
            "href": reverse("platform:profile-settings"),
        },
        {
            "title": "Поддержка",
            "description": "Связаться с командой Sadaka в Telegram.",
            "href": site_meta.support_bot_url if site_meta else "",
        },
    ]

    return {
        "profile_identity": {
            "display_name": display_name,
            "primary_contact": primary_contact,
            "initials": _build_profile_initials(user),
            "member_since": user.date_joined,
            "phone": user.phone,
        },
        "invite_link": invite_link,
        "telegram_profile": telegram_profile,
        "profile_overview": {
            "total_donated": total_donated,
            "successful_donations_count": len(successful_donations),
            "active_subscriptions_count": len(active_subscriptions),
            "monthly_commitment": monthly_commitment,
            "latest_support_at": latest_support.paid_at if latest_support and latest_support.paid_at else latest_support.created_at if latest_support else None,
            "member_since": user.date_joined,
            "invited_count": referral_overview["invited_count"],
            "referral_rank": referral_overview["rank"],
            "referred_payments_total": referral_overview["referred_payments_total"],
            "referred_payments_count": referral_overview["referred_payments_count"],
        },
        "profile_recent_support": recent_support,
        "profile_recent_notifications": recent_notifications,
        "profile_unread_notifications_count": Notification.objects.filter(user=user, is_read=False).count(),
        "profile_quick_actions": [item for item in quick_actions if item["href"]],
        "referral_leaderboard": referral_leaderboard,
        "referral_overview": referral_overview,
        "profile_donations": [
            {
                "amount": donation.amount,
                "date": donation.paid_at or donation.created_at,
                "status": donation.get_status_display(),
                "mosque_name": donation.mosque.name,
                "project_title": donation.project.title if donation.project_id else "",
                "payment_method": donation.get_payment_method_display(),
                "receipt_number": donation.receipt_number,
            }
            for donation in donations
        ],
        "profile_subscriptions": [
            {
                "amount": subscription.amount,
                "status": subscription.get_status_display(),
                "mosque_name": subscription.mosque.name,
                "project_title": subscription.project.title if subscription.project_id else "",
                "next_charge_date": subscription.next_charge_date,
                "payment_method": subscription.get_payment_method_display() if hasattr(subscription, "get_payment_method_display") else subscription.payment_method,
                "provider_subscription_id": subscription.provider_subscription_id,
            }
            for subscription in active_subscriptions
        ],
    }
