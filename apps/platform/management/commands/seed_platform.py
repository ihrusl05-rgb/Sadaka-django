from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.content.models import ContentItem
from apps.mosques.models import Mosque, MosqueDocument, MosqueExpenseItem, MosqueGalleryImage, MosqueMembership, MosquePartner
from apps.platform.models import PlatformSettings
from apps.projects.models import Project
from apps.users.models import User


class Command(BaseCommand):
    help = "Seed initial platform data"

    def handle(self, *args, **options):
        platform_admin_password = "admin12345"
        platform_admin, _ = User.objects.get_or_create(
            email="admin@sadaka.local",
            defaults={
                "full_name": "Platform Admin",
                "role": User.Role.PLATFORM_ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
            },
        )
        if not platform_admin.check_password(platform_admin_password):
            platform_admin.set_password(platform_admin_password)
            platform_admin.save(update_fields=["password"])

        mosque_admin_password = "imam12345"
        mosque_admin, _ = User.objects.get_or_create(
            email="imam@sadaka.local",
            defaults={
                "full_name": "Mosque Admin",
                "role": User.Role.MOSQUE_ADMIN,
                "is_email_verified": True,
            },
        )
        if not mosque_admin.check_password(mosque_admin_password):
            mosque_admin.set_password(mosque_admin_password)
            mosque_admin.save(update_fields=["password"])

        PlatformSettings.objects.get_or_create(
            pk=1,
            defaults={
                "site_name": "Sadaka",
                "support_email": "support@sadaka.local",
                "default_commission_percent": Decimal("5.00"),
                "donations_enabled": True,
            },
        )

        mosque, _ = Mosque.objects.get_or_create(
            slug="central-mosque",
            defaults={
                "name": "Central Mosque",
                "description": "Main seeded mosque profile.",
                "public_story": "Публичная страница мечети с описанием текущего сбора и жизни общины.",
                "city": "Kazan",
                "address": "1 Tatarstan Street",
                "contact_email": "central@sadaka.local",
                "contact_phone": "+79990000000",
                "legal_name": "МЕСТНАЯ МУСУЛЬМАНСКАЯ РЕЛИГИОЗНАЯ ОРГАНИЗАЦИЯ",
                "inn": "1650000000",
                "kpp": "165001001",
                "ogrn": "1021600000000",
                "bank_account": "40703810000000000001",
                "bank_name": "ПАО СБЕРБАНК",
                "bik": "049205603",
                "corr_account": "30101810400000000603",
                "legal_address": "г. Казань, ул. Тестовая, д. 1",
                "actual_address": "г. Казань, ул. Тестовая, д. 1",
                "okpo": "12345678",
                "oktmo": "92701000",
                "okato": "92401385000",
                "verification_status": Mosque.VerificationStatus.VERIFIED,
                "moderation_status": Mosque.ModerationStatus.APPROVED,
                "created_by": mosque_admin,
            },
        )
        MosqueMembership.objects.get_or_create(mosque=mosque, user=mosque_admin, defaults={"is_primary": True})

        project, _ = Project.objects.get_or_create(
            slug="roof-restoration",
            defaults={
                "mosque": mosque,
                "created_by": mosque_admin,
                "title": "Roof Restoration",
                "description": "Repair and waterproofing of the mosque roof.",
                "status": Project.Status.ACTIVE,
                "goal_amount": Decimal("1000000.00"),
            },
        )
        if mosque.featured_project_id != project.id:
            mosque.featured_project = project
            mosque.save(update_fields=["featured_project"])

        ContentItem.objects.get_or_create(
            slug="platform-launch",
            defaults={
                "author": platform_admin,
                "title": "Platform Launch",
                "body": "Sadaka platform is ready for demo usage.",
                "type": ContentItem.Type.NEWS,
                "scope": ContentItem.Scope.PLATFORM,
                "moderation_status": ContentItem.ModerationStatus.APPROVED,
                "is_published": True,
            },
        )

        MosqueExpenseItem.objects.get_or_create(
            mosque=mosque,
            title="Ремонт кровли",
            defaults={"amount": Decimal("350000.00"), "sort_order": 10},
        )
        MosqueExpenseItem.objects.get_or_create(
            mosque=mosque,
            title="Отделочные работы",
            defaults={"amount": Decimal("220000.00"), "sort_order": 20},
        )
        MosqueDocument.objects.get_or_create(
            mosque=mosque,
            title="Агентский договор",
            defaults={"file": "mosques/documents/agent-contract.txt", "sort_order": 10},
        )
        MosquePartner.objects.get_or_create(
            mosque=mosque,
            name="Sadaka",
            defaults={"website_url": "https://sadaka.local", "sort_order": 10},
        )
        MosqueGalleryImage.objects.get_or_create(
            mosque=mosque,
            caption="Основной зал мечети",
            defaults={"image": "mosques/gallery/gallery.jpg", "sort_order": 10},
        )

        self.stdout.write(self.style.SUCCESS("Seed data created."))
