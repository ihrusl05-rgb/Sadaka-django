import factory
from factory.django import DjangoModelFactory

from apps.mosques.models import Mosque, MosqueDocument, MosqueExpenseItem, MosqueGalleryImage, MosqueMembership, MosquePartner
from apps.projects.models import Project
from apps.users.models import MaxAccount, TelegramAccount, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    role = User.Role.USER
    is_email_verified = True

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        raw_password = extracted or "StrongPass123!"
        obj.set_password(raw_password)
        if create:
            obj.save(update_fields=["password"])


class MosqueFactory(DjangoModelFactory):
    class Meta:
        model = Mosque

    name = factory.Sequence(lambda n: f"Mosque {n}")
    description = "Mosque profile"
    city = "Kazan"
    address = "Main street"
    contact_email = factory.Sequence(lambda n: f"mosque{n}@example.com")
    contact_phone = "+79990000000"
    verification_status = Mosque.VerificationStatus.VERIFIED
    moderation_status = Mosque.ModerationStatus.APPROVED


class MosqueMembershipFactory(DjangoModelFactory):
    class Meta:
        model = MosqueMembership

    mosque = factory.SubFactory(MosqueFactory)
    user = factory.SubFactory(UserFactory, role=User.Role.MOSQUE_ADMIN)
    is_primary = True


class ProjectFactory(DjangoModelFactory):
    class Meta:
        model = Project

    mosque = factory.SubFactory(MosqueFactory)
    created_by = factory.SubFactory(UserFactory, role=User.Role.MOSQUE_ADMIN)
    title = factory.Sequence(lambda n: f"Project {n}")
    description = "Project description"
    status = Project.Status.ACTIVE
    goal_amount = "1000.00"


class TelegramAccountFactory(DjangoModelFactory):
    class Meta:
        model = TelegramAccount

    user = factory.SubFactory(UserFactory)
    telegram_id = factory.Sequence(lambda n: 100000000 + n)
    chat_id = factory.LazyAttribute(lambda obj: obj.telegram_id)
    username = factory.Sequence(lambda n: f"sadaka_user_{n}")


class MaxAccountFactory(DjangoModelFactory):
    class Meta:
        model = MaxAccount

    user = factory.SubFactory(UserFactory)
    max_user_id = factory.Sequence(lambda n: 200000000 + n)
    chat_id = factory.LazyAttribute(lambda obj: obj.max_user_id)
    username = factory.Sequence(lambda n: f"sadaka_max_{n}")


class MosqueExpenseItemFactory(DjangoModelFactory):
    class Meta:
        model = MosqueExpenseItem

    mosque = factory.SubFactory(MosqueFactory)
    title = factory.Sequence(lambda n: f"Expense {n}")
    amount = "50000.00"
    sort_order = factory.Sequence(lambda n: n)


class MosqueDocumentFactory(DjangoModelFactory):
    class Meta:
        model = MosqueDocument

    mosque = factory.SubFactory(MosqueFactory)
    title = factory.Sequence(lambda n: f"Document {n}")
    file = factory.django.FileField(filename="document.txt", data=b"test document")
    sort_order = factory.Sequence(lambda n: n)


class MosqueGalleryImageFactory(DjangoModelFactory):
    class Meta:
        model = MosqueGalleryImage

    mosque = factory.SubFactory(MosqueFactory)
    image = factory.django.ImageField(filename="gallery.jpg")
    caption = factory.Sequence(lambda n: f"Gallery {n}")
    sort_order = factory.Sequence(lambda n: n)


class MosquePartnerFactory(DjangoModelFactory):
    class Meta:
        model = MosquePartner

    mosque = factory.SubFactory(MosqueFactory)
    name = factory.Sequence(lambda n: f"Partner {n}")
    website_url = factory.Sequence(lambda n: f"https://partner{n}.example.com")
    logo = factory.django.ImageField(filename="partner.jpg")
    sort_order = factory.Sequence(lambda n: n)
