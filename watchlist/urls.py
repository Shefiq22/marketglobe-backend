from django.urls import path

from . import views

urlpatterns = [
    path("", views.WatchlistListView.as_view(), name="watchlist_list"),
    path("<int:pk>/", views.WatchlistDetailView.as_view(), name="watchlist_detail"),
    path("<int:pk>/add/", views.WatchlistAddAssetView.as_view(), name="watchlist_add_asset"),
    path(
        "<int:pk>/remove/<int:asset_id>/",
        views.WatchlistRemoveAssetView.as_view(),
        name="watchlist_remove_asset",
    ),
]
