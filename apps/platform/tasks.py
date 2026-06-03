from celery import shared_task

from apps.platform.services import PlatformSettingsService


@shared_task
def ensure_platform_settings_task():
    PlatformSettingsService.get_settings()
