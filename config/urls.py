from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/assets/", include("assets.urls")),
    path("api/predictions/", include("predictions.urls")),
    path("api/news/", include("news.urls")),
    path("api/watchlist/", include("watchlist.urls")),
]
