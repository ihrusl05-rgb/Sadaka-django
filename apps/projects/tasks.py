from celery import shared_task

from apps.projects.services import ProjectService


@shared_task
def recompute_project_current_amount_task(project_id: int):
    ProjectService.recompute_current_amount(project_id=project_id)
