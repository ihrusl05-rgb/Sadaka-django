from celery import shared_task

from apps.projects.services import ProjectService


@shared_task
def recompute_mosque_aggregates_task(mosque_id: int):
    ProjectService.recompute_mosque_aggregates(mosque_id=mosque_id)
