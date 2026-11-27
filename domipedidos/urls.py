from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('users.urls')),
    path('', include('menu.urls')),
    path('', include('pedidos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Corregir el enlace /Quit detectado por la terminal en desarrollo.
from django.conf import settings as _settings
from django.urls import path as _path
from django.views.generic import RedirectView as _RedirectView

if _settings.DEBUG:
    urlpatterns += [
        _path("Quit", _RedirectView.as_view(pattern_name="home")),
    ]
