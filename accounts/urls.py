from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.EmailOrUsernameTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("settings/", views.UserSettingsView.as_view(), name="user_settings"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("reset-password/", views.ResetPasswordView.as_view(), name="reset_password"),
    path("request-otp/", views.RequestOtpView.as_view(), name="request_otp"),
    path("verify-otp/", views.VerifyOtpView.as_view(), name="verify_otp"),
    path("google/", views.GoogleLoginView.as_view(), name="google_login"),
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("2fa/verify/", views.TwoFactorVerifyView.as_view(), name="two_factor_verify"),
    path("2fa/disable/", views.TwoFactorDisableView.as_view(), name="two_factor_disable"),
    path("2fa/login/", views.TwoFactorLoginView.as_view(), name="two_factor_login"),
]
