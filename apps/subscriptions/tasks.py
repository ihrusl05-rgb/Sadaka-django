from celery import shared_task
from django.utils import timezone

from apps.subscriptions.models import Subscription
from apps.subscriptions.services import SubscriptionService


@shared_task
def process_due_subscriptions_task():
    due_subscriptions = Subscription.objects.filter(
        status=Subscription.Status.ACTIVE, next_charge_date__lte=timezone.localdate()
    )
    for subscription in due_subscriptions:
        SubscriptionService.process_due_subscription(subscription=subscription)
