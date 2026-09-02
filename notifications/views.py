from rest_framework import generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import AppNotification
from .serializers import AppNotificationSerializer
from .services import materialize_news


class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/ — the signed-in user's in-app notifications.

    Materializes fresh market-news notifications for the user on every call so
    the badge stays in sync with newly published headlines, then returns the
    list (newest first).
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AppNotificationSerializer

    def get_queryset(self):
        materialize_news(self.request.user)
        return AppNotification.objects.filter(user=self.request.user)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    """GET /api/notifications/unread-count/ — how many notifications are unread."""
    materialize_news(request.user)
    count = AppNotification.objects.filter(user=request.user, is_read=False).count()
    return Response({"count": count})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def mark_read(request):
    """POST /api/notifications/mark-read/ — mark notifications as read.

    Body: {"all": true} to mark everything read, or {"ids": [1, 2, 3]} to mark
    a specific set. Always returns the remaining unread count.
    """
    user = request.user
    ids = request.data.get("ids") or []
    mark_all = bool(request.data.get("all", False))

    qs = AppNotification.objects.filter(user=user, is_read=False)
    if not mark_all and ids:
        qs = qs.filter(id__in=ids)
    qs.update(is_read=True)

    remaining = AppNotification.objects.filter(user=user, is_read=False).count()
    return Response({"count": remaining})