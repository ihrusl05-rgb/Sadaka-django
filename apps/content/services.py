from django.utils import timezone

from apps.content.models import ContentItem
from apps.platform.services import AuditLogService


class ContentService:
    @staticmethod
    def create_content(*, actor, **payload) -> ContentItem:
        item = ContentItem.objects.create(author=actor, **payload)
        AuditLogService.log(action="content.created", obj=item, actor=actor)
        return item

    @staticmethod
    def update_content(*, item: ContentItem, actor, **payload) -> ContentItem:
        for field, value in payload.items():
            setattr(item, field, value)
        item.save()
        AuditLogService.log(action="content.updated", obj=item, actor=actor)
        return item

    @staticmethod
    def approve(*, item: ContentItem, actor) -> ContentItem:
        item.moderation_status = ContentItem.ModerationStatus.APPROVED
        item.is_published = True
        item.published_at = item.published_at or timezone.now()
        item.save(update_fields=["moderation_status", "is_published", "published_at", "updated_at"])
        AuditLogService.log(action="content.approved", obj=item, actor=actor)
        return item

    @staticmethod
    def reject(*, item: ContentItem, actor) -> ContentItem:
        item.moderation_status = ContentItem.ModerationStatus.REJECTED
        item.save(update_fields=["moderation_status", "updated_at"])
        AuditLogService.log(action="content.rejected", obj=item, actor=actor)
        return item
