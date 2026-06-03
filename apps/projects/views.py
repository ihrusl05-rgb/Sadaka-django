from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.projects.filters import ProjectFilterSet
from apps.projects.permissions import ProjectAccessPermission
from apps.projects.selectors import get_projects_for_actor
from apps.projects.serializers import ProjectSerializer
from apps.projects.services import ProjectService
from common.permissions import CanModerateObject, IsMosqueAdmin
from common.utils.auth import get_actor_or_anonymous


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    filterset_class = ProjectFilterSet
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "goal_amount", "current_amount", "published_at"]

    def get_permissions(self):
        if self.action in {"approve", "reject", "block"}:
            return [CanModerateObject()]
        if self.action == "create":
            return [IsMosqueAdmin()]
        return [ProjectAccessPermission()]

    def get_queryset(self):
        return get_projects_for_actor(actor=get_actor_or_anonymous(self.request.user))

    def perform_create(self, serializer):
        serializer.instance = ProjectService.create_project(actor=self.request.user, **serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = ProjectService.update_project(
            project=self.get_object(), actor=self.request.user, **serializer.validated_data
        )

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        project = ProjectService.approve(project=self.get_object(), actor=request.user)
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        project = ProjectService.reject(project=self.get_object(), actor=request.user)
        return Response(self.get_serializer(project).data)

    @action(detail=True, methods=["post"])
    def block(self, request, pk=None):
        project = ProjectService.block(project=self.get_object(), actor=request.user)
        return Response(self.get_serializer(project).data)
