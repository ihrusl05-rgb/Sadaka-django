from django.urls import path
from django.urls import include

from apps.platform.views import AboutPageView, GuestDonationView, GuestSubscriptionView, HelpPageView, LandingPageView, MosqueWidgetRequestView, MosquesCatalogView, NamazCitySearchView, NamazDataView, NamazLocateView, NamazPageView, PublicMosqueDetailView
from apps.users.web_views import LogoutView, ProfileHistoryView, ProfileSettingsView, ProfileSubscriptionsView, ProfileTelegramConnectView, ProfileView, TelegramLoginView

app_name = "platform"

urlpatterns = [
    path("", include("apps.notifications.urls")),
    path("", LandingPageView.as_view(), name="landing"),
    path("api/landing/mosque-request/", MosqueWidgetRequestView.as_view(), name="mosque-widget-request"),
    path("api/landing/namaz/search/", NamazCitySearchView.as_view(), name="namaz-search"),
    path("api/landing/namaz/locate/", NamazLocateView.as_view(), name="namaz-locate"),
    path("api/landing/namaz/data/", NamazDataView.as_view(), name="namaz-data"),
    path("mosques/", MosquesCatalogView.as_view(), name="mosques"),
    path("namaz/", NamazPageView.as_view(), name="namaz"),
    path("help/", HelpPageView.as_view(), name="help"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/history/", ProfileHistoryView.as_view(), name="profile-history"),
    path("profile/subscriptions/", ProfileSubscriptionsView.as_view(), name="profile-subscriptions"),
    path("profile/settings/", ProfileSettingsView.as_view(), name="profile-settings"),
    path("profile/settings/telegram/connect/", ProfileTelegramConnectView.as_view(), name="profile-telegram-connect"),
    path("login/", TelegramLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("mosques/<slug:slug>/", PublicMosqueDetailView.as_view(), name="public-mosque-detail"),
    path("donate/guest/", GuestDonationView.as_view(), name="guest-donation"),
    path("subscribe/guest/", GuestSubscriptionView.as_view(), name="guest-subscription"),
]
