import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token


User = get_user_model()


class AccountsApiTests(TestCase):
    def test_signup_api_creates_user_and_returns_profile_and_token(self):
        url = reverse("accounts:api_signup")
        payload = {
            "username": "api_alice",
            "email": "alice@example.com",
            "password1": "aStrongPassw0rd!",
            "password2": "aStrongPassw0rd!",
            "organization_name": "Alice Corp",
            "job_title": "Founder",
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIn("token", body)
        self.assertEqual(body["data"]["username"], "api_alice")
        self.assertTrue(User.objects.filter(username="api_alice").exists())

    def test_signup_api_returns_errors_for_invalid_payload(self):
        url = reverse("accounts:api_signup")
        response = self.client.post(
            url,
            data=json.dumps({"username": "short"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("password1", body["errors"])

    def test_login_api_authenticates_user_and_returns_token(self):
        User.objects.create_user(username="api_bob", password="aStrongPassw0rd!")
        url = reverse("accounts:api_login")
        response = self.client.post(
            url,
            data=json.dumps(
                {"username": "api_bob", "password": "aStrongPassw0rd!"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["username"], "api_bob")
        self.assertIn("token", body)

    def test_login_api_rejects_bad_credentials(self):
        url = reverse("accounts:api_login")
        response = self.client.post(
            url,
            data=json.dumps(
                {"username": "api_bob", "password": "wrongpass"}
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIn("non_field_errors", body["errors"])

    def test_logout_api_requires_auth_and_revokes_token(self):
        user = User.objects.create_user(
            username="api_carol", password="aStrongPassw0rd!"
        )
        token = Token.objects.create(user=user)

        url = reverse("accounts:api_logout")
        response = self.client.post(
            url, HTTP_AUTHORIZATION=f"Token {token.key}"
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertFalse(Token.objects.filter(user=user).exists())

        unauth_response = self.client.post(url)
        self.assertEqual(unauth_response.status_code, 401)
