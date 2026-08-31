from django.urls import path

from . import views

urlpatterns = [
    path("", views.AssetListView.as_view(), name="asset_list"),
    path("<int:pk>/", views.AssetDetailView.as_view(), name="asset_detail"),
]
