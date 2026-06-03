from django.db import migrations, models


def _column_names(schema_editor, table_name: str) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    return {column.name for column in description}


def sync_notification_columns(apps, schema_editor):
    table_name = "notifications_notification"
    columns = _column_names(schema_editor, table_name)

    rename_map = {
        "type": "notification_type",
        "body": "message",
        "data": "payload",
    }
    for old_name, new_name in rename_map.items():
        if old_name in columns and new_name not in columns:
            schema_editor.execute(
                schema_editor.sql_rename_column
                % {
                    "table": schema_editor.quote_name(table_name),
                    "old_column": schema_editor.quote_name(old_name),
                    "new_column": schema_editor.quote_name(new_name),
                    "type": "",
                }
            )
            columns.remove(old_name)
            columns.add(new_name)


def normalize_notification_types(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    Notification.objects.exclude(notification_type__in=["info", "success", "warning", "error"]).update(notification_type="info")


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0003_alter_notification_options_alter_notification_body_and_more"),
    ]

    operations = [
        migrations.RunPython(sync_notification_columns, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.RenameField(
                    model_name="notification",
                    old_name="type",
                    new_name="notification_type",
                ),
                migrations.RenameField(
                    model_name="notification",
                    old_name="body",
                    new_name="message",
                ),
                migrations.RenameField(
                    model_name="notification",
                    old_name="data",
                    new_name="payload",
                ),
            ],
        ),
        migrations.RunPython(normalize_notification_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="notification",
            name="channel",
        ),
        migrations.RemoveField(
            model_name="notification",
            name="sent_at",
        ),
        migrations.AddField(
            model_name="notification",
            name="event",
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name="Событие"),
        ),
        migrations.AddField(
            model_name="notification",
            name="is_sound_enabled",
            field=models.BooleanField(default=True, verbose_name="Звук включен"),
        ),
        migrations.AddField(
            model_name="notification",
            name="link",
            field=models.CharField(blank=True, max_length=500, verbose_name="Ссылка"),
        ),
        migrations.AddField(
            model_name="notification",
            name="sound_key",
            field=models.CharField(default="default", max_length=64, verbose_name="Ключ звука"),
        ),
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[("info", "Информация"), ("success", "Успех"), ("warning", "Предупреждение"), ("error", "Ошибка")],
                db_index=True,
                default="info",
                max_length=16,
                verbose_name="Тип уведомления",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="is_read",
            field=models.BooleanField(db_index=True, default=False, verbose_name="Прочитано"),
        ),
        migrations.AlterField(
            model_name="notification",
            name="message",
            field=models.TextField(verbose_name="Сообщение"),
        ),
        migrations.AlterField(
            model_name="notification",
            name="payload",
            field=models.JSONField(blank=True, default=dict, verbose_name="Служебные данные"),
        ),
        migrations.AlterField(
            model_name="notification",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="notifications",
                to="users.user",
                verbose_name="Пользователь",
            ),
        ),
        migrations.AlterModelOptions(
            name="notification",
            options={"ordering": ["-created_at"], "verbose_name": "уведомление", "verbose_name_plural": "уведомления"},
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "is_read"], name="notificatio_user_id_427e4b_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "created_at"], name="notificatio_user_id_c62b26_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["event"], name="notificatio_event_0ebdc5_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["notification_type"], name="notificatio_notific_f2898f_idx"),
        ),
    ]
