from django.urls import path

from . import views

urlpatterns = [
    path("", views.PredictionListView.as_view(), name="prediction_list"),
    path("metrics/", views.ModelMetricListView.as_view(), name="model_metrics"),
    path("<int:pk>/", views.PredictionDetailView.as_view(), name="prediction_detail"),
    path("refresh/<int:asset_id>/", views.refresh_prediction, name="refresh_prediction"),
]
