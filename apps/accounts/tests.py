from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


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

# Create your tests here.
