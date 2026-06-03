from celery import shared_task

from apps.users.services import UserService


@shared_task
def send_password_reset_task(email: str):
    UserService.initiate_password_reset(email=email)
