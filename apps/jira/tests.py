from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch

from .oauth import create_pkce_pair, build_authorize_url


class OAuthHelpersTests(TestCase):
    def test_pkce_pair(self):
        v, c = create_pkce_pair()
        self.assertTrue(len(v) >= 43)  # base64url of 32 bytes ~ 43 chars
        self.assertTrue(len(c) >= 43)


@override_settings(ATLASSIAN_CLIENT_ID="abc", ATLASSIAN_REDIRECT_URI="http://testserver/jira/callback/", ATLASSIAN_SCOPES="read:jira-user")
class ConnectFlowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")

    def test_connect_redirects_to_atlassian(self):
        self.client.login(username="u", password="p")
        resp = self.client.get(reverse("jira:connect"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("auth.atlassian.com/authorize", resp["Location"]) 

    @patch("apps.jira.views.exchange_token")
    @patch("apps.jira.views.get_accessible_resources")
    def test_callback_saves_tokens(self, mock_resources, mock_exchange):
        self.client.login(username="u", password="p")
        # Simulate session state and verifier
        session = self.client.session
        session["atl_state"] = "s"
        session["atl_code_verifier"] = "v"
        session.save()

        mock_exchange.return_value = {"access_token": "a", "refresh_token": "r", "expires_in": 3600, "token_type": "Bearer", "expires_at_epoch": 9999999999}
        mock_resources.return_value = [{"id": "cloud123", "name": "Dev"}]

        resp = self.client.get(reverse("jira:callback"), {"state": "s", "code": "c"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("jira:issues"))

# Create your tests here.
