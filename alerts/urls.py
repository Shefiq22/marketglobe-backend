from django.urls import path

from . import views

urlpatterns = [
    path("", views.AlertListView.as_view(), name="alert_list"),
    path("<int:pk>/", views.AlertDetailView.as_view(), name="alert_detail"),
    path("check/", views.AlertCheckView.as_view(), name="alert_check"),
]
