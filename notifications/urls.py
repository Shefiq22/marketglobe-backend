from django.urls import path

from . import views

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="notifications"),
    path("unread-count/", views.unread_count, name="notifications_unread"),
    path("mark-read/", views.mark_read, name="notifications_mark_read"),
]