from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="MarketGlobe API",
        default_version="v1",
        description="Pulse Markets backend API",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API documentation (Swagger UI + ReDoc + raw schema)
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("swagger<format>/", schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-root"),
    path("api/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-api"),
    path("api/auth/", include("accounts.urls")),
    path("api/assets/", include("assets.urls")),
    path("api/predictions/", include("predictions.urls")),
    path("api/news/", include("news.urls")),
    path("api/watchlist/", include("watchlist.urls")),
]
