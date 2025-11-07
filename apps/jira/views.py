import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.http import HttpResponseBadRequest, HttpResponse
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from .models import AtlassianConnection
from .oauth import (
    create_pkce_pair,
    build_authorize_url,
    exchange_token,
    get_accessible_resources,
    refresh_access_token,
    api_request,
    API_BASE,
)
import requests


@login_required
def connect(request):
    if not settings.ATLASSIAN_CLIENT_ID:
        return HttpResponse("Atlassian client not configured", status=500)
    state = _random_state()
    verifier, challenge = create_pkce_pair()
    request.session["atl_state"] = state
    request.session["atl_code_verifier"] = verifier
    auth_url = build_authorize_url(state, challenge)
    return redirect(auth_url)


def _random_state() -> str:
    import secrets

    return secrets.token_urlsafe(16)


def _flatten_adf_node(node: Any) -> str:
    if isinstance(node, dict):
        node_type = node.get("type")
        if node_type == "text":
            return node.get("text", "")
        if node_type == "hardBreak":
            return "\n"
        content = node.get("content", [])
        child_text = [_flatten_adf_node(child) for child in content]
        if node_type in {"bulletList", "orderedList"}:
            items = [text.strip("\n") for text in child_text if text]
            return "\n".join(items)
        return "".join(child_text)
    if isinstance(node, list):
        return "".join(_flatten_adf_node(child) for child in node)
    return ""


def _adf_to_plaintext(document: Any) -> str:
    if isinstance(document, str):
        return document
    if not isinstance(document, dict):
        return ""
    blocks = []
    for node in document.get("content", []):
        block_text = _flatten_adf_node(node)
        if block_text:
            blocks.append(block_text.strip("\n"))
    return "\n\n".join(blocks)


def _plaintext_to_adf(text: str) -> dict[str, Any]:
    lines = text.split("\n")
    content: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        if line:
            content.append({"type": "text", "text": line})
        if index < len(lines) - 1:
            content.append({"type": "hardBreak"})
    if not content:
        content = [{"type": "text", "text": ""}]
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": content}],
    }


def _pick_jira_resource(resources):
    """Return the first accessible Jira resource, if any."""
    for resource in resources:
        resource_type = (resource.get("resourceType") or "").lower()
        scopes = resource.get("scopes") or []
        is_jira_scope = any("jira" in scope for scope in scopes)
        if resource_type == "jira" or is_jira_scope:
            if resource.get("id") or resource.get("cloudId"):
                return resource
    return None


@login_required
def callback(request):
    state = request.GET.get("state")
    code = request.GET.get("code")
    if not state or not code:
        return HttpResponseBadRequest("Missing state or code")
    if state != request.session.get("atl_state"):
        return HttpResponseBadRequest("Invalid state")
    verifier = request.session.get("atl_code_verifier")
    if not verifier:
        return HttpResponseBadRequest("Missing code verifier")

    try:
        token = exchange_token(code, verifier)
    except requests.HTTPError as e:
        resp = e.response
        detail = resp.text if resp is not None else str(e)
        return HttpResponse(f"Token exchange failed ({getattr(resp,'status_code', 'error')}): {detail}", status=getattr(resp,'status_code', 400))
    resources = get_accessible_resources(token["access_token"])
    jira_res = _pick_jira_resource(resources) or (resources[0] if resources else None)
    conn, _ = AtlassianConnection.objects.get_or_create(user=request.user)
    conn.access_token = token.get("access_token", "")
    conn.refresh_token = token.get("refresh_token", "")
    conn.token_type = token.get("token_type", "")
    conn.scope = settings.ATLASSIAN_SCOPES
    if jira_res:
        conn.cloud_id = jira_res.get("id") or jira_res.get("cloudId", "")
        conn.cloud_name = jira_res.get("name", "")
    # expires_at
    expires_epoch = token.get("expires_at_epoch")
    if expires_epoch:
        conn.expires_at = datetime.fromtimestamp(expires_epoch, tz=timezone.utc)
    conn.save()
    # Cleanup
    request.session.pop("atl_state", None)
    request.session.pop("atl_code_verifier", None)
    return redirect("jira:issues")


def _ensure_access_token(conn: AtlassianConnection) -> str:
    # If token is within 60s of expiry, refresh
    if conn.expires_at and conn.expires_at.timestamp() - time.time() < 60 and conn.refresh_token:
        data = refresh_access_token(conn.refresh_token)
        conn.access_token = data.get("access_token", conn.access_token)
        conn.refresh_token = data.get("refresh_token", conn.refresh_token)
        if "expires_at_epoch" in data:
            conn.expires_at = datetime.fromtimestamp(data["expires_at_epoch"], tz=timezone.utc)
        conn.save(update_fields=["access_token", "refresh_token", "expires_at", "updated_at"])
    return conn.access_token


@login_required
def issues(request):
    conn = getattr(request.user, "atlassian_connection", None)
    if not conn or not conn.access_token or not conn.cloud_id:
        return render(request, "jira/connect.html")
    access_token = _ensure_access_token(conn)
    # Fetch current user's issues
    params = {
        "jql": "assignee=currentUser() ORDER BY updated DESC",
        "fields": "summary,status,assignee,updated,issuetype,labels,reporter,development", # Added issuetype here
        "maxResults": 50,
    }
    url = f"{API_BASE}/ex/jira/{conn.cloud_id}/rest/api/3/search/jql"
    r = api_request(access_token, "GET", url, params=params)
    if r.status_code == 410:
        resources = get_accessible_resources(access_token)
        jira_res = _pick_jira_resource(resources)
        new_cloud_id = (jira_res.get("id") if jira_res else None) or ""
        if new_cloud_id and new_cloud_id != conn.cloud_id:
            conn.cloud_id = new_cloud_id
            if jira_res.get("name"):
                conn.cloud_name = jira_res.get("name")
            conn.save(update_fields=["cloud_id", "cloud_name", "updated_at"])
            url = f"{API_BASE}/ex/jira/{conn.cloud_id}/rest/api/3/search/jql"
            r = api_request(access_token, "GET", url, params=params)
    r.raise_for_status()
    data = r.json()
    raw_issues: Iterable[dict[str, Any]] = data.get("issues", []) or []

    enriched_issues: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    latest_update = None

    for raw in raw_issues:
        if not isinstance(raw, dict):
            continue

        fields = raw.get("fields") or {}
        status_info = fields.get("status") or {}
        status_name = (status_info.get("name") or "Unknown").strip() or "Unknown"
        status_slug = slugify(status_name) or "unknown"

        issue_type_info = fields.get("issuetype") or {}
        issue_type_name = (issue_type_info.get("name") or "Issue").strip() or "Issue"
        issue_type_slug = slugify(issue_type_name) or "issue"

        labels = [label for label in (fields.get("labels") or []) if label]
        development = fields.get("development") or {}

        updated_raw = fields.get("updated")
        updated_dt = parse_datetime(updated_raw) if updated_raw else None
        if updated_dt and (latest_update is None or updated_dt > latest_update):
            latest_update = updated_dt

        summary = fields.get("summary") or ""
        assignee = (fields.get("assignee") or {}).get("displayName") or "Unassigned"
        reporter = (fields.get("reporter") or {}).get("displayName") or ""

        status_counts[status_name] += 1
        type_counts[issue_type_name] += 1

        enriched_issues.append(
            {
                "key": raw.get("key", ""),
                "summary": summary,
                "status": status_name,
                "status_slug": status_slug,
                "status_category": (status_info.get("statusCategory") or {}).get("key") or "",
                "issue_type": issue_type_name,
                "issue_type_slug": issue_type_slug,
                "assignee": assignee,
                "reporter": reporter,
                "labels": labels,
                "development": {
                    "branch": development.get("branch") if isinstance(development, dict) else None,
                    "commit": development.get("commit") if isinstance(development, dict) else None,
                    "pull_request": development.get("pullRequest") if isinstance(development, dict) else None,
                },
                "updated": updated_dt,
                "updated_raw": updated_raw,
                "search_blob": " ".join(
                    filter(
                        None,
                        [
                            str(raw.get("key", "")),
                            summary,
                            " ".join(labels),
                            assignee,
                            reporter,
                        ],
                    )
                ).lower(),
            }
        )

    status_summary = [
        {"name": name, "count": count, "slug": slugify(name) or "unknown"}
        for name, count in status_counts.most_common()
    ]
    type_summary = [
        {"name": name, "count": count, "slug": slugify(name) or "issue"}
        for name, count in type_counts.most_common()
    ]

    return render(
        request,
        "jira/issues_list.html",
        {
            "issues": enriched_issues,
            "cloud_name": conn.cloud_name,
            "status_summary": status_summary,
            "type_summary": type_summary,
            "total_issues": len(enriched_issues),
            "latest_update": latest_update,
        },
    )


@login_required
def edit_issue(request, key: str):
    conn = getattr(request.user, "atlassian_connection", None)
    if not conn or not conn.access_token or not conn.cloud_id:
        return redirect("jira:issues")
    access_token = _ensure_access_token(conn)
    # On GET: fetch issue details
    issue_url = f"{API_BASE}/ex/jira/{conn.cloud_id}/rest/api/3/issue/{key}"
    if request.method == "POST":
        summary = (request.POST.get("summary") or "").strip()
        raw_description = request.POST.get("description")
        description_text = (raw_description or "").strip()
        payload = {"fields": {}}
        if summary:
            payload["fields"]["summary"] = summary
        if raw_description is not None:
            payload["fields"]["description"] = (
                _plaintext_to_adf(description_text) if description_text else None
            )
        if payload["fields"]:
            r = api_request(access_token, "PUT", issue_url, json=payload)
            if r.status_code not in (200, 204):
                return HttpResponse(f"Failed to update: {r.text}", status=r.status_code)
        return redirect("jira:issues")

    r = api_request(access_token, "GET", issue_url, params={"fields": "summary,description"})
    r.raise_for_status()
    issue = r.json()
    fields = issue.get("fields", {})
    description_value = fields.get("description", "")
    return render(
        request,
        "jira/issue_edit.html",
        {
            "key": key,
            "summary": fields.get("summary", ""),
            "description": _adf_to_plaintext(description_value),
        },
    )


@login_required
def delete_issue(request, key: str):
    conn = getattr(request.user, "atlassian_connection", None)
    if not conn or not conn.access_token or not conn.cloud_id:
        return redirect("jira:issues")
    access_token = _ensure_access_token(conn)
    issue_url = f"{API_BASE}/ex/jira/{conn.cloud_id}/rest/api/3/issue/{key}"

    if request.method == "POST":
        response = api_request(access_token, "DELETE", issue_url)
        if response.status_code not in (200, 204):
            return HttpResponse(f"Failed to delete: {response.text}", status=response.status_code)
        return redirect("jira:issues")

    response = api_request(access_token, "GET", issue_url, params={"fields": "summary"})
    if response.status_code == 404:
        return HttpResponse("Issue not found", status=404)
    response.raise_for_status()
    issue = response.json()
    summary = issue.get("fields", {}).get("summary", "")
    return render(
        request,
        "jira/issue_confirm_delete.html",
        {
            "key": key,
            "summary": summary,
        },
    )


# Create your views here.
