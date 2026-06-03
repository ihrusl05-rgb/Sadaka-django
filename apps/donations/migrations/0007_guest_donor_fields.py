from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("donations", "0006_alter_donation_options_alter_donation_amount_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="donation",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name="donations",
                to="users.user",
                verbose_name="Жертвователь",
            ),
        ),
        migrations.AddField(
            model_name="donation",
            name="guest_email",
            field=models.EmailField(blank=True, default="", max_length=254, verbose_name="Email гостя"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="donation",
            name="guest_full_name",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Имя гостя"),
            preserve_default=False,
        ),
    ]
