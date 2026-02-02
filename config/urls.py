from django.contrib import admin
from django.urls import path, include
from core.views import HealthCheckView
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/auth/', include('authx.urls')),
    path('api/events/', include('events.urls')),
    path('api/core/', include('core.urls')),
    path('api/ux/', include('ux.urls')),
    path('api/ncos/', include('projects.urls')), # n-COS Module
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
]
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
