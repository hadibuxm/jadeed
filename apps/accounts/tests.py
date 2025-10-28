from urllib.parse import quote

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AccountsViewsTests(TestCase):
    def test_index_route_200(self):
        url = reverse("accounts:index")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Accounts home")

    def test_signup_creates_user_and_redirects_to_login(self):
        url = reverse("accounts:signup")
        data = {
            "username": "alice",
            "email": "alice@example.com",
            "password1": "aStrongPassw0rd!",
            "password2": "aStrongPassw0rd!",
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts:login"))
        User = get_user_model()
        self.assertTrue(User.objects.filter(username="alice").exists())

    def test_login_redirects_to_index(self):
        # Create a user
        User = get_user_model()
        user = User.objects.create_user(
            username="bob", password="aStrongPassw0rd!"
        )
        url = reverse("accounts:login")
        resp = self.client.post(url, {"username": "bob", "password": "aStrongPassw0rd!"})
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse("accounts:index"))
        # Follow and ensure authenticated navigation shows logout
        follow = self.client.get(reverse("accounts:index"))
        self.assertContains(follow, "Sign out")


class HomeRedirectTests(TestCase):
    def test_home_redirects_anonymous_user_to_login(self):
        resp = self.client.get("/")
        login_url = reverse("accounts:login")
        expected_url = f"{login_url}?next={quote('/')}"
        self.assertRedirects(resp, expected_url, target_status_code=200)

    def test_home_redirects_authenticated_user_to_jira_issues(self):
        User = get_user_model()
        user = User.objects.create_user(
            username="carol", password="aStrongPassw0rd!"
        )
        self.client.force_login(user)
        resp = self.client.get("/")
        self.assertRedirects(resp, reverse("jira:issues"), target_status_code=200)

# Create your tests here.
