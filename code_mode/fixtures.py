"""Synthetic, nonproduction source data for the offline pilot."""

from code_mode.bridge import FixtureMCPClient

PILOT_RESPONSES: dict[str, object] = {
    "github.list_issues": [
        {
            "number": 101,
            "title": "Staging migration blocked",
            "state": "open",
            "labels": ["blocker", "backend"],
            "url": "https://example.invalid/issues/101",
        },
        {
            "number": 102,
            "title": "Update runbook",
            "state": "open",
            "labels": ["docs"],
            "url": "https://example.invalid/issues/102",
        },
    ],
    "github.list_pull_requests": [
        {
            "number": 77,
            "title": "Migration fix",
            "state": "open",
            "draft": True,
            "url": "https://example.invalid/pulls/77",
        }
    ],
    "github.ci_status": {
        "ref": "staging",
        "status": "completed",
        "conclusion": "failure",
        "url": "https://example.invalid/actions/5",
    },
    "railway.list_deployments": [
        {
            "id": "dep-1",
            "service": "backend",
            "environment": "staging",
            "status": "failed",
            "created_at": "2026-11-20T12:00:00Z",
        }
    ],
    "railway.service_status": {
        "service": "backend",
        "environment": "staging",
        "status": "degraded",
        "deployment_id": "dep-1",
    },
}

PILOT_CODE = """
const issues = await tools.call('github.list_issues', {});
const prs = await tools.call('github.list_pull_requests', {});
const ci = await tools.call('github.ci_status', {});
const deployments = await tools.call('railway.list_deployments', {});
const service = await tools.call('railway.service_status', {});
return {
  open_issue_count: issues.filter(i => i.state === 'open').length,
  blockers: issues.filter(i => i.labels.includes('blocker'))
    .map(i => ({number: i.number, title: i.title})),
  open_pr_count: prs.filter(p => p.state === 'open').length,
  ci_conclusion: ci.conclusion,
  staging_service: service.status,
  failed_deployments: deployments.filter(d => d.status === 'failed').map(d => d.id)
};
"""


def fixture_client() -> FixtureMCPClient:
    return FixtureMCPClient(PILOT_RESPONSES)
