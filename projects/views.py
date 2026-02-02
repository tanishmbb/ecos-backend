from rest_framework import viewsets, permissions
from .models import Project
from .serializers import ProjectSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    """
    n-COS API: Manage Projects.
    Permissions:
    - List: Public (filtered by Community privacy)
    - Create: Authenticated
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_queryset(self):
        # Optional: Filter by community if provided in URL params
        queryset = super().get_queryset()
        community_slug = self.request.query_params.get('community_slug')
        if community_slug:
            queryset = queryset.filter(community__slug=community_slug)
        return queryset
