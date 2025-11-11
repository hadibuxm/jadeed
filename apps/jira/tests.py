from django.test import TestCase, override_settings, SimpleTestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch

from .oauth import create_pkce_pair, build_authorize_url
from .views import _adf_to_plaintext, _plaintext_to_adf
from .models import AtlassianConnection


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
        mock_resources.return_value = [{"id": "cloud123", "name": "Dev", "resourceType": "jira"}]

        resp = self.client.get(reverse("jira:callback"), {"state": "s", "code": "c"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("jira:issues"))

    @patch("apps.jira.views.exchange_token")
    @patch("apps.jira.views.get_accessible_resources")
    def test_callback_prefers_jira_resource(self, mock_resources, mock_exchange):
        self.client.login(username="u", password="p")
        session = self.client.session
        session["atl_state"] = "s"
        session["atl_code_verifier"] = "v"
        session.save()

        mock_exchange.return_value = {
            "access_token": "a",
            "refresh_token": "r",
            "expires_in": 3600,
            "token_type": "Bearer",
            "expires_at_epoch": 9999999999,
        }
        mock_resources.return_value = [
            {
                "id": "conf-123",
                "name": "Conf",
                "resourceType": "confluence",
                "scopes": ["read:confluence-space.summary"],
            },
            {
                "id": "jira-456",
                "name": "Jira Cloud",
                "resourceType": "jira",
                "scopes": ["read:jira-user"],
            },
        ]

        self.client.get(reverse("jira:callback"), {"state": "s", "code": "c"})
        conn = AtlassianConnection.objects.get(user=self.user)
        self.assertEqual(conn.cloud_id, "jira-456")
        self.assertEqual(conn.cloud_name, "Jira Cloud")


@override_settings(
    ATLASSIAN_CLIENT_ID="abc",
    ATLASSIAN_REDIRECT_URI="http://testserver/jira/callback/",
    ATLASSIAN_SCOPES="read:jira-user read:jira-work",
)
class IssuesViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="u", password="p")
        self.connection = AtlassianConnection.objects.create(
            user=self.user,
            access_token="token",
            refresh_token="refresh",
            cloud_id="conf-123",
            cloud_name="Conf",
        )

    @staticmethod
    def _sample_issue(key="ISSUE-1", summary="Sample summary", status="To Do", issue_type="Task"):
        return {
            "key": key,
            "fields": {
                "summary": summary,
                "status": {
                    "name": status,
                    "statusCategory": {"key": "new"},
                },
                "issuetype": {"name": issue_type},
                "assignee": {"displayName": "Owner"},
                "reporter": {"displayName": "Reporter"},
                "labels": ["triaged"],
                "development": {},
                "updated": "2024-01-01T00:00:00.000+0000",
            },
        }

    @patch("apps.jira.views.api_request")
    @patch("apps.jira.views.get_accessible_resources")
    @patch("apps.jira.views._ensure_access_token")
    def test_issues_recovers_from_410(self, mock_ensure, mock_resources, mock_api):
        def make_response(status, payload=None):
            class FakeResponse:
                def __init__(self, status_code, data):
                    self.status_code = status_code
                    self._data = data or {}

                def json(self):
                    return self._data

                def raise_for_status(self):
                    pass

            return FakeResponse(status, payload)

        mock_ensure.return_value = "access-token"
        mock_resources.return_value = [
            {
                "id": "jira-456",
                "name": "Jira Cloud",
                "resourceType": "jira",
                "scopes": ["read:jira-user"],
            }
        ]
        mock_api.side_effect = [
            make_response(410),
            make_response(200, {"issues": [self._sample_issue()]}),
        ]

        self.client.login(username="u", password="p")
        resp = self.client.get(reverse("jira:issues"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["total_issues"], 1)
        self.assertEqual(resp.context["issues"][0]["key"], "ISSUE-1")
        self.assertEqual(resp.context["issues"][0]["status"], "To Do")
        self.assertEqual(resp.context["status_summary"][0]["name"], "To Do")
        self.assertEqual(resp.context["cloud_name"], "Jira Cloud")
        self.connection.refresh_from_db()
        self.assertEqual(self.connection.cloud_id, "jira-456")
        self.assertEqual(mock_api.call_count, 2)
        first_call_url = mock_api.call_args_list[0].args[2]
        second_call_url = mock_api.call_args_list[1].args[2]
        self.assertIn("/search/jql", first_call_url)
        self.assertIn("/search/jql", second_call_url)
        self.assertIn("conf-123", first_call_url)
        self.assertIn("jira-456", second_call_url)


class DescriptionConversionTests(SimpleTestCase):
    def test_plaintext_to_adf_round_trip(self):
        text = "Line one\nLine two"
        document = _plaintext_to_adf(text)
        self.assertEqual(document["type"], "doc")
        self.assertEqual(document["version"], 1)
        self.assertEqual(_adf_to_plaintext(document), text)

    def test_adf_to_plaintext_handles_empty(self):
        self.assertEqual(_adf_to_plaintext(None), "")
        self.assertEqual(_adf_to_plaintext({"type": "doc", "content": []}), "")


@override_settings(
    ATLASSIAN_CLIENT_ID="abc",
    ATLASSIAN_REDIRECT_URI="http://testserver/jira/callback/",
    ATLASSIAN_SCOPES="read:jira-user read:jira-work",
)
class DeleteIssueViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="deleter", password="p")
        self.connection = AtlassianConnection.objects.create(
            user=self.user,
            access_token="token",
            refresh_token="refresh",
            cloud_id="conf-123",
            cloud_name="Conf",
        )

    @staticmethod
    def _make_response(status_code, payload=None):
        class FakeResponse:
            def __init__(self, code, data):
                self.status_code = code
                self._data = data or {}
                self.text = ""

            def json(self):
                return self._data

            def raise_for_status(self):
                pass

        return FakeResponse(status_code, payload)

    @patch("apps.jira.views.api_request")
    @patch("apps.jira.views._ensure_access_token")
    def test_get_renders_confirmation(self, mock_ensure, mock_api):
        mock_ensure.return_value = "access-token"
        mock_api.return_value = self._make_response(200, {"fields": {"summary": "Clean up issue"}})

        self.client.login(username="deleter", password="p")
        resp = self.client.get(reverse("jira:issue_delete", args=["ISSUE-5"]))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["summary"], "Clean up issue")
        request_args = mock_api.call_args
        self.assertEqual(request_args.args[1], "GET")
        self.assertIn("/issue/ISSUE-5", request_args.args[2])

    @patch("apps.jira.views.api_request")
    @patch("apps.jira.views._ensure_access_token")
    def test_post_deletes_and_redirects(self, mock_ensure, mock_api):
        mock_ensure.return_value = "access-token"
        mock_api.return_value = self._make_response(204)

        self.client.login(username="deleter", password="p")
        resp = self.client.post(reverse("jira:issue_delete", args=["ISSUE-5"]))

        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp["Location"], reverse("jira:issues"))
        request_args = mock_api.call_args
        self.assertEqual(request_args.args[1], "DELETE")
        self.assertIn("/issue/ISSUE-5", request_args.args[2])

# Create your tests here.
