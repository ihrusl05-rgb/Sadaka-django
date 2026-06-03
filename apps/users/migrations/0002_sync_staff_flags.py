from django.db import migrations


def sync_staff_flags(apps, schema_editor):
    User = apps.get_model("users", "User")
    for user in User.objects.all():
        if user.is_superuser:
            if not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
            continue
        user.is_staff = user.role in {"mosque_admin", "platform_admin"}
        user.save(update_fields=["is_staff"])


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_staff_flags, migrations.RunPython.noop),
    ]
