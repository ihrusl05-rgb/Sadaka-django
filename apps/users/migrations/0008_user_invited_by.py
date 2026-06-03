from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_telegramaccount_telegramauthcode_telegramlogintoken_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="invited_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="invited_users",
                to="users.user",
                verbose_name="Пригласивший пользователь",
            ),
        ),
    ]
