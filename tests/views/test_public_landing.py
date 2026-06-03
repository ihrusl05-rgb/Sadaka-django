from decimal import Decimal

import pytest
from django.urls import reverse

from apps.donations.models import Donation
from apps.platform.views import REFERRAL_SESSION_KEY
from apps.support.notifications import SupportNotificationError
from apps.subscriptions.models import Subscription
from apps.users.max_auth import MaxAuthService
from apps.users.telegram_auth import TelegramAuthService
from tests.factories import MosqueDocumentFactory, MosqueExpenseItemFactory, MosqueFactory, MosqueGalleryImageFactory, MosquePartnerFactory, ProjectFactory, UserFactory


@pytest.mark.django_db
def test_public_routes_render(client):
    response = client.get(reverse("platform:landing"))
    mosque = MosqueFactory()

    assert response.status_code == 200
    html = response.content.decode()
    assert "SJ." not in html
    assert "Садака Джария" in html
    assert "Поиск" in html
    assert "Мечети" in html
    assert "Намаз" in html
    assert "Помощь" in html
    assert "О нас" in html
    assert "Стать партнером" in html
    assert reverse("platform:mosques") in html
    assert reverse("platform:namaz") in html
    assert reverse("platform:help") in html
    assert reverse("platform:about") in html
    assert 'href="#how">Как работает садака джария</a>' in html
    assert "Сейчас совершают садака" in html
    assert "Совершай садака джария —" in html
    assert "награда, которая не прекращается" in html
    assert "Поиск мечети" not in html
    assert "Все мечети" in html
    assert "landing/home-hero-mosque.png" in html
    assert "branding/favicon.png" in html
    assert "branding/sj-brand-mark.png" in html
    assert "landing/steps/step-1.png" in html
    assert "Прозрачные пожертвования · История операций · Публичные отчёты" not in html
    assert "Первые пожертвования появятся здесь после оплаты" not in html
    assert "Платформа пожертвований" not in html
    assert "Поддержка мечетей" not in html
    assert "Каталог" not in html
    assert "Мечетей в сервисе" not in html
    assert "Собрано открыто" not in html
    assert "Помогли сегодня" not in html

    detail_response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))
    mosques_response = client.get(reverse("platform:mosques"))
    help_response = client.get(reverse("platform:help"))
    namaz_response = client.get(reverse("platform:namaz"))
    about_response = client.get(reverse("platform:about"))

    subscribe_response = client.get(reverse("platform:guest-subscription"))
    donate_response = client.get(reverse("platform:guest-donation"))

    assert detail_response.status_code == 200
    assert mosques_response.status_code == 200
    assert help_response.status_code == 200
    assert namaz_response.status_code == 200
    assert about_response.status_code == 200
    assert subscribe_response.status_code == 200
    assert donate_response.status_code == 302
    assert donate_response.headers["Location"] == reverse("platform:guest-subscription")
    assert "Садака Джария" in detail_response.content.decode()
    mosques_html = mosques_response.content.decode()
    help_html = help_response.content.decode()
    namaz_html = namaz_response.content.decode()
    about_html = about_response.content.decode()
    assert "Мечети на платформе" in mosques_html
    assert "Все публичные мечети" not in mosques_html
    assert "оценок" not in mosques_html
    assert "Частые вопросы" in help_html
    assert "Не нашли свою мечеть?" in help_html
    assert "Добавляйте мечеть!" in help_html
    assert "Новая мечеть в каталоге" not in help_html
    assert "Намаз" in namaz_html
    assert "Время намаза по вашему городу" in namaz_html
    assert "Определить мой город" in namaz_html
    assert "Ближайшие важные даты" in namaz_html
    assert "Садака Джария" in about_html
    assert "О платформе" in about_html
    assert "Сотрудничество" in about_html
    assert 'href="#contacts"' not in about_html
    assert "<h2>Контакты</h2>" not in about_html
    assert "Единый центр поддержки" in about_html
    assert "Садака Джария" in subscribe_response.content.decode()


@pytest.mark.django_db
def test_public_header_renders_login_button_for_guest(client):
    response = client.get(reverse("platform:landing"))

    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("platform:login") in html
    assert "data-mosque-widget-root" in html
    assert reverse("platform:mosque-widget-request") in html
    assert "Добавить мечеть" in html
    assert "Обязательные поля: название мечети, город и телефон для связи." in html


@pytest.mark.django_db
def test_namaz_search_returns_results(client, monkeypatch):
    monkeypatch.setattr(
        "apps.platform.views.search_locations",
        lambda **kwargs: [
            {
                "city": "Казань",
                "region": "Татарстан",
                "country": "Россия",
                "country_code": "RU",
                "lat": 55.7946,
                "lon": 49.1115,
                "label": "Казань, Татарстан",
                "description": "Казань, Татарстан, Россия",
            }
        ],
    )

    response = client.get(reverse("platform:namaz-search"), {"q": "Каз"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["results"][0]["city"] == "Казань"
    assert payload["results"][0]["country_code"] == "RU"


@pytest.mark.django_db
def test_namaz_search_rejects_short_query(client):
    response = client.get(reverse("platform:namaz-search"), {"q": "К"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "2 символа" in payload["message"]


@pytest.mark.django_db
def test_namaz_locate_returns_location(client, monkeypatch):
    monkeypatch.setattr(
        "apps.platform.views.reverse_location",
        lambda **kwargs: {
            "city": "Екатеринбург",
            "region": "Свердловская область",
            "country": "Россия",
            "country_code": "RU",
            "lat": 56.8389,
            "lon": 60.6057,
            "label": "Екатеринбург, Свердловская область",
            "description": "Екатеринбург, Свердловская область, Россия",
        },
    )

    response = client.get(reverse("platform:namaz-locate"), {"lat": "56.8389", "lon": "60.6057"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["location"]["city"] == "Екатеринбург"
    assert payload["location"]["country_code"] == "RU"


@pytest.mark.django_db
def test_namaz_locate_requires_coordinates(client):
    response = client.get(reverse("platform:namaz-locate"), {"lat": "x", "lon": ""})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "координаты" in payload["message"]


@pytest.mark.django_db
def test_namaz_data_returns_payload(client, monkeypatch):
    monkeypatch.setattr(
        "apps.platform.views.get_namaz_payload",
        lambda **kwargs: {
            "location": {
                "city": "Казань",
                "region": "Татарстан",
                "country": "Россия",
                "country_code": "RU",
                "lat": 55.7946,
                "lon": 49.1115,
                "label": "Казань, Татарстан",
            },
            "timezone": "Europe/Moscow",
            "timings": {
                "Fajr": "02:30 (MSK)",
                "Sunrise": "04:45 (MSK)",
                "Dhuhr": "12:25 (MSK)",
                "Asr": "16:20 (MSK)",
                "Maghrib": "20:05 (MSK)",
                "Isha": "22:10 (MSK)",
            },
            "gregorian_date": "19 мая 2026",
            "hijri_date": "1 Зуль-хиджа 1447",
            "hijri_year": 1447,
            "next_prayer": {
                "key": "Maghrib",
                "label": "Магриб",
                "time": "20:05",
            },
            "calendar": [
                {
                    "title": "Курбан-байрам",
                    "note": "Праздник жертвоприношения",
                    "gregorian": "27 мая 2026",
                    "hijri": "10 Зуль-хиджа 1447",
                }
            ],
            "month_schedule": {
                "month": "Май",
                "year": 2026,
                "rows": [
                    {
                        "day": 19,
                        "weekday": "вт",
                        "fajr": "02:30",
                        "sunrise": "04:45",
                        "dhuhr": "12:25",
                        "asr": "16:20",
                        "maghrib": "20:05",
                        "isha": "22:10",
                        "gregorian": "19 мая 2026",
                        "hijri": "1 Зуль-хиджа 1447",
                    }
                ],
            },
        },
    )

    response = client.get(
        reverse("platform:namaz-data"),
        {
            "lat": "55.7946",
            "lon": "49.1115",
            "city": "Казань",
            "region": "Татарстан",
            "country": "Россия",
            "country_code": "RU",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["location"]["city"] == "Казань"
    assert payload["timings"]["Fajr"] == "02:30 (MSK)"
    assert payload["next_prayer"]["key"] == "Maghrib"
    assert payload["calendar"][0]["title"] == "Курбан-байрам"
    assert payload["month_schedule"]["rows"][0]["day"] == 19


@pytest.mark.django_db
def test_namaz_data_requires_coordinates(client):
    response = client.get(reverse("platform:namaz-data"), {"lat": "abc", "lon": ""})

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "координаты" in payload["message"]


@pytest.mark.django_db
def test_public_header_widget_does_not_render_address_field(client):
    response = client.get(reverse("platform:landing"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Телефон для связи" in html
    assert "Город / населённый пункт" in html
    assert "Адрес мечети" not in html


@pytest.mark.django_db
def test_mosque_widget_request_returns_success_json(client, monkeypatch):
    captured = {}

    def fake_send(**payload):
        captured.update(payload)

    monkeypatch.setattr("apps.platform.views.send_mosque_widget_request_notification", fake_send)

    response = client.post(
        reverse("platform:mosque-widget-request"),
        data={
            "mosque_name": "Мечеть Нур",
            "city": "Казань",
            "applicant_name": "Ильдар",
            "contact": "+79990000000",
            "comment": "Районная мечеть",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert "Спасибо" in payload["message"]
    assert captured["request_snapshot"]["mosque_name"] == "Мечеть Нур"
    assert captured["request_snapshot"]["city"] == "Казань"
    assert captured["request_snapshot"]["full_name"] == "Ильдар"
    assert captured["request_snapshot"]["phone"] == "+79990000000"
    assert captured["request_snapshot"]["comment"] == "Районная мечеть"


@pytest.mark.django_db
def test_mosque_widget_request_accepts_json_payload(client, monkeypatch):
    monkeypatch.setattr("apps.platform.views.send_mosque_widget_request_notification", lambda **kwargs: None)

    response = client.post(
        reverse("platform:mosque-widget-request"),
        data='{"mosque_name":"Мечеть Ихлас","city":"Уфа","contact":"+79990000000"}',
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.django_db
def test_mosque_widget_request_returns_validation_errors(client):
    response = client.post(
        reverse("platform:mosque-widget-request"),
        data={"mosque_name": "", "city": "", "contact": ""},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert "mosque_name" in payload["errors"]
    assert "city" in payload["errors"]
    assert "contact" in payload["errors"]


@pytest.mark.django_db
def test_mosque_widget_request_rejects_non_phone_contact(client):
    response = client.post(
        reverse("platform:mosque-widget-request"),
        data={
            "mosque_name": "Мечеть Нур",
            "city": "Казань",
            "contact": "@ildar",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["errors"]["contact"][0]["message"] == "Укажите номер телефона в формате +7XXXXXXXXXX."


@pytest.mark.django_db
def test_mosque_widget_request_rejects_ten_digit_phone(client):
    response = client.post(
        reverse("platform:mosque-widget-request"),
        data={
            "mosque_name": "Мечеть Нур",
            "city": "Казань",
            "contact": "9990000000",
        },
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["errors"]["contact"][0]["message"] == "Укажите номер телефона в формате +7XXXXXXXXXX."


@pytest.mark.django_db
def test_public_header_renders_logout_button_for_authenticated_user(client):
    user = UserFactory()
    client.force_login(user)

    response = client.get(reverse("platform:landing"))

    assert response.status_code == 200
    html = response.content.decode()
    assert reverse("platform:profile") in html
    assert "Выйти" not in html
    assert user.email not in html


@pytest.mark.django_db
def test_public_mosque_detail_renders_full_header_for_authenticated_user(client):
    user = UserFactory()
    mosque = MosqueFactory()
    client.force_login(user)

    response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Поиск" in html
    assert "Мечети" in html
    assert "Намаз" in html
    assert "Помощь" in html
    assert "О нас" in html
    assert "Стать партнером" in html
    assert reverse("platform:profile") in html


@pytest.mark.django_db
def test_telegram_login_page_requests_and_verifies_code(client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_test_bot"
    settings.MAX_AUTH_BOT_USERNAME = "id025404324718_5_bot"
    login_url = reverse("platform:login")

    initial_response = client.get(login_url)
    initial_html = initial_response.content.decode()
    assert "Вход через Telegram" in initial_html
    assert "Войти через Telegram" in initial_html
    assert "Войти через VK" not in initial_html
    assert "Войти через MAX" in initial_html
    assert "Откройте бота, получите одноразовый код" in initial_html
    assert "Три простых шага" in initial_html

    request_response = client.post(
        login_url,
        data={"action": "start_telegram", "next": reverse("platform:landing")},
    )

    assert request_response.status_code == 302
    assert request_response.url == login_url
    token = client.session["telegram_login_token"]

    pending_response = client.get(login_url)
    pending_html = pending_response.content.decode()
    assert "Откройте Telegram-бота" in pending_html
    assert "Ожидаем подтверждение в Telegram" in pending_html

    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=123456789,
        chat_id=123456789,
        username="sadaka_user",
        first_name="Ильдар",
    )
    code_result = TelegramAuthService.issue_code(token=token, send_message=False)

    page_response = client.get(login_url)
    page_html = page_response.content.decode()
    assert "Введите код из Telegram" in page_html
    assert "@sadaka_user" in page_html
    assert "Подтвердить вход" in page_html

    verify_response = client.post(
        login_url,
        data={"action": "verify_code", "code": code_result.raw_code, "next": reverse("platform:landing")},
    )

    assert verify_response.status_code == 302
    assert verify_response.url == reverse("platform:landing")
    assert "_auth_user_id" in client.session
    assert client.session.get("telegram_login_token") is None
    landing_response = client.get(reverse("platform:landing"))
    assert "Вход выполнен успешно" not in landing_response.content.decode()
    assert "Вы вышли из аккаунта" not in landing_response.content.decode()


@pytest.mark.django_db
def test_telegram_login_without_next_redirects_to_profile(client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_test_bot"
    login_url = reverse("platform:login")

    request_response = client.post(login_url, data={"action": "start_telegram"})

    assert request_response.status_code == 302
    assert request_response.url == login_url
    token = client.session["telegram_login_token"]

    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=111111111,
        chat_id=111111111,
        username="profile_redirect_user",
        first_name="Ильдар",
    )
    code_result = TelegramAuthService.issue_code(token=token, send_message=False)

    verify_response = client.post(
        login_url,
        data={"action": "verify_code", "code": code_result.raw_code},
    )

    assert verify_response.status_code == 302
    assert verify_response.url == reverse("platform:profile")


@pytest.mark.django_db
def test_email_password_login_from_web_form_redirects_to_profile(client):
    user = UserFactory(email="web-login@example.com")

    response = client.post(
        reverse("platform:login"),
        data={
            "action": "email_login",
            "email": "web-login@example.com",
            "password": "StrongPass123!",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("platform:profile")
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_referral_link_is_saved_in_session_and_bound_after_telegram_login(client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_test_bot"
    inviter = UserFactory(full_name="Пригласивший Пользователь")
    landing_url = f"{reverse('platform:landing')}?ref=user-{inviter.pk}"
    login_url = reverse("platform:login")

    landing_response = client.get(landing_url)

    assert landing_response.status_code == 200
    assert client.session[REFERRAL_SESSION_KEY] == inviter.pk

    start_response = client.post(login_url, data={"action": "start_telegram"})
    assert start_response.status_code == 302
    token = client.session["telegram_login_token"]

    TelegramAuthService.confirm_login_token(
        token=token,
        telegram_id=222222222,
        chat_id=222222222,
        username="ref_joined_user",
        first_name="Реф",
    )
    code_result = TelegramAuthService.issue_code(token=token, send_message=False)

    verify_response = client.post(login_url, data={"action": "verify_code", "code": code_result.raw_code})
    assert verify_response.status_code == 302

    referred_user = inviter.invited_users.get()
    assert referred_user.telegram_account.username == "ref_joined_user"


@pytest.mark.django_db
def test_telegram_login_ajax_start_returns_json_payload(client, settings):
    settings.TELEGRAM_AUTH_BOT_USERNAME = "sadaka_test_bot"
    login_url = reverse("platform:login")

    response = client.post(
        login_url,
        data={"action": "start_telegram", "next": reverse("platform:landing")},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["redirect_url"] == reverse("platform:login")
    assert "sadaka_test_bot" in payload["telegram_url"]
    assert "login_" in payload["telegram_url"]
    assert client.session["telegram_login_token"]


@pytest.mark.django_db
def test_max_login_page_requests_and_verifies_code(client, settings):
    settings.MAX_AUTH_BOT_USERNAME = "id025404324718_5_bot"
    login_url = reverse("platform:login")

    initial_response = client.get(login_url)
    initial_html = initial_response.content.decode()
    assert "Войти через MAX" in initial_html

    request_response = client.post(
        login_url,
        data={"action": "start_max", "next": reverse("platform:landing")},
    )

    assert request_response.status_code == 302
    assert request_response.url == login_url
    token = client.session["telegram_login_token"]

    pending_response = client.get(login_url)
    pending_html = pending_response.content.decode()
    assert "Откройте MAX-бота" in pending_html
    assert "Ожидаем подтверждение в MAX" in pending_html

    MaxAuthService.confirm_login_token(
        token=token,
        max_user_id=333222111,
        chat_id=333222111,
        username="sadaka_max_user",
        first_name="Амир",
    )
    code_result = MaxAuthService.issue_code(token=token, send_message=False)

    page_response = client.get(login_url)
    page_html = page_response.content.decode()
    assert "Введите код из MAX" in page_html
    assert "@sadaka_max_user" in page_html

    verify_response = client.post(
        login_url,
        data={"action": "verify_code", "code": code_result.raw_code, "next": reverse("platform:landing")},
    )

    assert verify_response.status_code == 302
    assert verify_response.url == reverse("platform:landing")
    assert "_auth_user_id" in client.session
    assert client.session.get("telegram_login_token") is None


@pytest.mark.django_db
def test_profile_page_renders_new_layout_for_authenticated_user(client):
    user = UserFactory(first_name="Ильдар", last_name="Ахметов")
    client.force_login(user)

    response = client.get(reverse("platform:profile"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Личный кабинет" in html
    assert "Выйти" in html
    assert "Свежие события" in html
    assert "Рейтинг по приглашениям" in html


@pytest.mark.django_db
def test_landing_renders_mosque_search_block_without_payment_controls(client):
    MosqueFactory(name="Туган Авылым", city="Казань", address="улица Тукая, 1")
    MosqueFactory(name="Ляля-Тюльпан", city="Уфа", address="улица Комарова, 5")

    response = client.get(reverse("platform:landing"))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="quick-donate"' in html
    assert "Найдите мечеть и станьте частью благого дела" in html
    assert "Выберите город" in html
    assert "Поиск по названию, адресу мечети..." in html
    assert ">Поиск<" in html
    assert "Мечети, которым можно помочь" not in html
    assert 'data-city-mosques-grid' in html
    assert 'data-mosque-search-form' in html
    assert 'data-city-select' in html
    assert 'data-mosque-query' in html
    assert 'data-city-mosques-block' in html
    assert 'data-public-mosque-form' not in html
    assert 'data-mode="once"' not in html
    assert "Своя сумма" not in html


@pytest.mark.django_db
def test_mosques_catalog_renders_live_search_without_fake_ratings(client):
    MosqueFactory(name="Нур", city="Казань", address="Улица 1", description="Центральная мечеть района")
    MosqueFactory(name="Ихлас", city="Уфа", address="Улица 2", description="Небольшая квартальная мечеть")

    response = client.get(reverse("platform:mosques"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Мечети на платформе" in html
    assert 'data-mosque-catalog-search' in html
    assert 'data-catalog-city-filter' in html
    assert 'data-catalog-query' in html
    assert 'data-mosque-catalog-grid' in html
    assert 'data-mosque-empty-shell' in html
    assert 'data-mosque-card' in html
    assert "Все города" in html
    assert "Оценок" not in html
    assert "оценок" not in html
    assert "Помочь" in html


@pytest.mark.django_db
def test_help_page_renders_faq_and_accepts_add_mosque_request(client):
    response = client.get(reverse("platform:help"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Частые вопросы" in html
    assert "Популярные" in html
    assert "Пожертвования" in html
    assert "Проекты" in html
    assert "Другое" in html
    assert "ФИО" in html
    assert "Добавить мечеть" in html

    captured = {}

    def fake_send_add_mosque_request_notification(**payload):
        captured.update(payload)

    from apps.platform import views as platform_views

    original_sender = platform_views.send_add_mosque_request_notification
    platform_views.send_add_mosque_request_notification = fake_send_add_mosque_request_notification

    try:
        post_response = client.post(
            reverse("platform:help"),
            data={
                "full_name": "Ильдар Ахметов",
                "mosque_name": "Мечеть Аль-Фатиха",
                "region": "Казань",
                "phone": "+79990000000",
            },
            follow=True,
        )
    finally:
        platform_views.send_add_mosque_request_notification = original_sender

    assert post_response.status_code == 200
    assert "Заявка отправлена. Мы перезвоним в течение 24 часов" in post_response.content.decode()
    assert captured["request_snapshot"]["full_name"] == "Ильдар Ахметов"
    assert captured["request_snapshot"]["mosque_name"] == "Мечеть Аль-Фатиха"
    assert captured["request_snapshot"]["region"] == "Казань"
    assert captured["request_snapshot"]["phone"] == "+79990000000"


@pytest.mark.django_db
def test_help_page_rejects_ten_digit_phone(client):
    response = client.post(
        reverse("platform:help"),
        data={
            "full_name": "Ильдар Ахметов",
            "mosque_name": "Мечеть Аль-Фатиха",
            "region": "Казань",
            "phone": "9990000000",
        },
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "Укажите номер телефона в формате +7XXXXXXXXXX." in html


@pytest.mark.django_db
def test_landing_renders_empty_search_state_when_no_public_mosques(client):
    response = client.get(reverse("platform:landing"))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Пока нет доступных городов" in html
    assert "Доступных мечетей пока нет. Загляните позже." in html
    assert 'data-city-mosques-grid' in html


@pytest.mark.django_db
def test_guest_donation_view_redirects_to_subscription_flow(client):
    mosque = MosqueFactory()

    response = client.post(
        reverse("platform:guest-donation"),
        data={
            "mosque": mosque.pk,
            "amount": "1500.00",
            "full_name": "Публичный Донор",
            "email": "",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("platform:guest-subscription")
    assert Donation.objects.count() == 0


@pytest.mark.django_db
def test_guest_subscription_view_creates_public_subscription(client):
    mosque = MosqueFactory()

    response = client.post(
        reverse("platform:guest-subscription"),
        data={
            "mosque": mosque.pk,
            "amount": "800.00",
            "full_name": "Регулярный Донор",
            "email": "",
        },
    )

    assert response.status_code == 302
    subscription = Subscription.objects.get(mosque=mosque)
    assert subscription.user is None
    assert subscription.guest_email == ""
    assert subscription.amount == Decimal("800.00")


@pytest.mark.django_db
def test_public_mosque_detail_view_prefills_query_params(client):
    mosque = MosqueFactory()
    ProjectFactory(mosque=mosque, title="Ремонт крыши")

    response = client.get(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={"amount": "3000", "mode": "monthly"},
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert 'value="3000"' in html
    assert 'value="monthly"' in html
    assert "Куда направить помощь" not in html


@pytest.mark.django_db
def test_public_mosque_detail_renders_single_custom_amount_input_and_gallery_lightbox(client):
    mosque = MosqueFactory()
    MosqueGalleryImageFactory(mosque=mosque, caption="Основной зал")

    response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Внести свою сумму" in html
    assert 'placeholder="Внести свою сумму"' in html
    assert 'data-custom-amount' not in html
    assert ">Своя<" not in html
    assert 'class="mosque-detail-main"' in html
    assert 'data-gallery-trigger' in html
    assert 'data-gallery-lightbox' in html
    assert ">Открыть фото<" not in html


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_public_donation(client):
    mosque = MosqueFactory()
    ProjectFactory(mosque=mosque, goal_amount="250000.00")

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "once",
            "amount": "1500.00",
            "payment_method": Donation.PaymentMethod.CARD,
            "full_name": "Публичный Донор",
            "email": "page@example.com",
            "is_public_anonymous": "on",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    donation = Donation.objects.get(mosque=mosque)
    assert donation.user is None
    assert donation.status == Donation.Status.SUCCEEDED
    assert donation.payment_method == Donation.PaymentMethod.CARD
    assert donation.project is None
    assert donation.guest_full_name == ""
    assert donation.guest_email == ""
    assert donation.is_public_anonymous is True


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_project_donation_for_selected_project(client):
    mosque = MosqueFactory()
    roof_project = ProjectFactory(mosque=mosque, title="Ремонт крыши", goal_amount="250000.00")
    fence_project = ProjectFactory(mosque=mosque, title="Ремонт забора", goal_amount="120000.00")
    mosque.featured_project = roof_project
    mosque.save(update_fields=["featured_project"])

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "once",
            "project": str(fence_project.id),
            "amount": "2100.00",
            "payment_method": Donation.PaymentMethod.CARD,
            "full_name": "Публичный Донор",
            "email": "",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    donation = Donation.objects.get(mosque=mosque, project=fence_project)
    assert donation.amount == Decimal("2100.00")


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_anonymous_public_donation_without_contact_fields(client):
    mosque = MosqueFactory()

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "once",
            "amount": "1500.00",
            "payment_method": Donation.PaymentMethod.CARD,
            "full_name": "",
            "email": "",
            "is_public_anonymous": "on",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    donation = Donation.objects.get(mosque=mosque)
    assert donation.user is None
    assert donation.status == Donation.Status.SUCCEEDED
    assert donation.guest_full_name == ""
    assert donation.guest_email == ""
    assert donation.is_public_anonymous is True


@pytest.mark.django_db
def test_public_mosque_detail_view_requires_contact_fields_for_non_anonymous_support(client):
    mosque = MosqueFactory()

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "once",
            "amount": "1500.00",
            "payment_method": Donation.PaymentMethod.CARD,
            "full_name": "",
            "email": "",
            "consent": "on",
        },
    )

    assert response.status_code == 200
    assert Donation.objects.count() == 0
    assert "Укажите имя и фамилию." in response.content.decode()


@pytest.mark.django_db
def test_authenticated_public_forms_are_prefilled_from_profile(client):
    user = UserFactory(
        email="phone_79990001122@phone-auth.sadaka.local",
        full_name="",
        last_name="Ахметов",
        first_name="Рустам",
        middle_name="Фаритович",
        phone="+79990001122",
        is_phone_verified=True,
    )
    user.__class__.objects.filter(pk=user.pk).update(full_name="")
    user.refresh_from_db()
    mosque = MosqueFactory()
    client.force_login(user)

    response = client.get(reverse("platform:guest-donation"), follow=True)
    detail_response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))

    assert response.status_code == 200
    response_html = response.content.decode()
    assert 'value="Ахметов Рустам Фаритович"' in response_html
    assert 'value="phone_79990001122@phone-auth.sadaka.local"' not in response_html
    assert 'title="Личные данные можно заполнить в профиле"' in response_html
    assert 'title="Необязательное поле."' in response_html
    assert "Необязательное поле.</div>" not in response_html
    assert detail_response.status_code == 200
    detail_html = detail_response.content.decode()
    assert 'value="Ахметов Рустам Фаритович"' in detail_html
    assert 'title="Личные данные можно заполнить в профиле"' in detail_html
    assert 'title="Необязательное поле."' in detail_html
    assert "Необязательное поле.</div>" not in detail_html


@pytest.mark.django_db
def test_authenticated_user_can_submit_public_donation_without_changing_profile(client):
    user = UserFactory(
        full_name="Ахметов Рустам Фаритович",
        last_name="Ахметов",
        first_name="Рустам",
        middle_name="Фаритович",
        email="rustam@example.com",
        phone="+79990001122",
        is_phone_verified=True,
    )
    mosque = MosqueFactory()
    client.force_login(user)

    response = client.post(
        reverse("platform:guest-donation"),
        data={
            "mosque": mosque.pk,
            "amount": "2200.00",
            "full_name": "Другое Имя",
            "email": "",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("platform:guest-subscription")
    user.refresh_from_db()
    assert Donation.objects.count() == 0
    assert user.full_name == "Ахметов Рустам Фаритович"


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_public_subscription(client):
    mosque = MosqueFactory()
    ProjectFactory(mosque=mosque, title="Ремонт крыши")

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "monthly",
            "amount": "800.00",
            "payment_method": Donation.PaymentMethod.SBP,
            "full_name": "Регулярный Донор",
            "email": "monthly-page@example.com",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    subscription = Subscription.objects.get(guest_email="monthly-page@example.com")
    assert subscription.user is None
    assert subscription.amount == Decimal("800.00")
    assert subscription.payment_method == Donation.PaymentMethod.SBP
    assert subscription.project is None


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_project_subscription_for_selected_project(client):
    mosque = MosqueFactory()
    project = ProjectFactory(mosque=mosque, title="Ремонт крыши", goal_amount="250000.00")

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "monthly",
            "project": str(project.id),
            "amount": "950.00",
            "payment_method": Donation.PaymentMethod.SBP,
            "full_name": "Регулярный Донор",
            "email": "monthly-page@example.com",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    subscription = Subscription.objects.get(project=project)
    assert subscription.amount == Decimal("950.00")


@pytest.mark.django_db
def test_public_mosque_detail_view_creates_anonymous_public_subscription_without_contact_fields(client):
    mosque = MosqueFactory()

    response = client.post(
        reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}),
        data={
            "mode": "monthly",
            "amount": "800.00",
            "payment_method": Donation.PaymentMethod.SBP,
            "full_name": "",
            "email": "",
            "is_public_anonymous": "on",
            "consent": "on",
        },
    )

    assert response.status_code == 302
    subscription = Subscription.objects.get(mosque=mosque)
    assert subscription.user is None
    assert subscription.amount == Decimal("800.00")
    assert subscription.guest_full_name == ""
    assert subscription.guest_email == ""
    assert subscription.is_public_anonymous is True


@pytest.mark.django_db
def test_public_mosque_detail_view_returns_404_for_non_public_mosque(client):
    mosque = MosqueFactory(
        verification_status="pending",
        moderation_status="pending",
        is_blocked=True,
    )

    response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_public_mosque_detail_hides_empty_sections_and_renders_filled_blocks(client):
    mosque = MosqueFactory(
        legal_name="Местная религиозная организация",
        inn="1234567890",
        public_story="История мечети " * 40,
    )
    active_project = ProjectFactory(mosque=mosque, title="Ремонт крыши", goal_amount="250000.00")
    ProjectFactory(mosque=mosque, title="Ремонт забора", goal_amount="120000.00")
    ProjectFactory(mosque=mosque, title="Архивный проект", goal_amount="50000.00", current_amount="50000.00", status="completed")
    mosque.featured_project = active_project
    mosque.save(update_fields=["featured_project"])
    MosqueExpenseItemFactory(mosque=mosque, title="Новая статья")
    MosqueGalleryImageFactory(mosque=mosque, caption="Галерея")
    MosqueDocumentFactory(mosque=mosque, title="Договор")
    MosquePartnerFactory(mosque=mosque, name="Партнер")

    response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": mosque.slug}))

    html = response.content.decode()
    assert "Проекты" in html
    assert "Ремонт крыши" in html
    assert "Ремонт забора" in html
    assert "Куда направить помощь" not in html
    assert "Полное описание" in html
    assert "Фотографии мечети" in html
    assert "Юридическая информация" in html
    assert "Скачать отчет" in html
    assert "Статьи расходов" not in html
    assert "Партнеры мечети" not in html

    empty_mosque = MosqueFactory()
    empty_response = client.get(reverse("platform:public-mosque-detail", kwargs={"slug": empty_mosque.slug}))
    empty_html = empty_response.content.decode()
    assert "Проекты" in empty_html
    assert "У этой мечети пока нет активных проектов." in empty_html
    assert "Статьи расходов" not in empty_html
    assert "Фотографии мечети" not in empty_html
    assert "Юридическая информация" in empty_html
    assert "Юридическая информация пока не добавлена." in empty_html
    assert "Партнеры мечети" not in empty_html
