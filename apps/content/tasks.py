from celery import shared_task

from apps.content.models import ContentItem
from apps.content.services import ContentService


@shared_task
def publish_content_item_task(content_item_id: int):
    item = ContentItem.objects.get(id=content_item_id)
    ContentService.approve(item=item, actor=item.author)
