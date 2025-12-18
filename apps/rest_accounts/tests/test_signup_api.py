import json
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from organizations.models import Organization


class JwtSignupViewTests(TestCase):
    def setUp(self):
        self.url = reverse("rest_accounts:api_signup")

    def _payload(self, **overrides):
        data = {
            "username": "new_owner",
            "email": "owner@example.com",
            "password1": "aStrongPassw0rd!",
            "password2": "aStrongPassw0rd!",
            "organization_name": "Acme Corp",
            "job_title": "Founder",
            "phone": "+15551234567",
        }
        data.update(overrides)
        return data

    def test_signup_rejects_duplicate_organization_name(self):
        Organization.objects.create(
            name="Acme Corp",
            slug="acme-corp",
            email="existing@example.com",
        )

        response = self.client.post(
            self.url,
            data=json.dumps(self._payload(username="another_user")),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("organization_name", body)
        self.assertIn("already exists", body["organization_name"][0])

    def test_signup_surfaces_integrity_error(self):
        with patch("apps.rest_accounts.views.create_user_with_organization") as mock_create:
            mock_create.side_effect = IntegrityError(
                "UNIQUE constraint failed: organizations_organization.name"
            )
            response = self.client.post(
                self.url,
                data=json.dumps(self._payload(username="different_user")),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn("organization_name", body)
        self.assertIn("already exists", body["organization_name"][0])
