from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.EmailOrUsernameTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("request-password-reset/", views.RequestPasswordResetView.as_view(), name="request_password_reset"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
    path("request-otp/", views.RequestOtpView.as_view(), name="request_otp"),
    path("verify-otp/", views.VerifyOtpView.as_view(), name="verify_otp"),
]
