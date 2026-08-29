"""Tests for the usage & billing-limits module (usage_service + /usage router)."""
from app.models.plan_limit import PlanLimit, PlanType
from app.services import usage_service


def test_new_user_gets_default_free_tier_plan_limit(db, test_user):
    """A user with no PlanLimit row yet gets a default free-tier plan on first access."""
    assert db.query(PlanLimit).filter(PlanLimit.user_id == test_user.id).first() is None

    plan_limit = usage_service.get_or_create_plan_limit(db, test_user.id)

    assert plan_limit.plan_type == PlanType.free
    assert plan_limit.monthly_minutes_limit == usage_service.DEFAULT_FREE_MONTHLY_MINUTES_LIMIT
    assert plan_limit.monthly_clips_limit == usage_service.DEFAULT_FREE_MONTHLY_CLIPS_LIMIT

    # Calling again returns the same row rather than creating a second one.
    plan_limit_again = usage_service.get_or_create_plan_limit(db, test_user.id)
    assert plan_limit_again.id == plan_limit.id
    assert db.query(PlanLimit).filter(PlanLimit.user_id == test_user.id).count() == 1


def test_get_my_usage_creates_default_plan_via_api(client, test_user, auth_headers):
    """GET /usage/me works for a brand-new user and returns free-tier defaults."""
    response = client.get("/api/v1/usage/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["plan_type"] == "free"
    assert body["monthly_minutes_limit"] == usage_service.DEFAULT_FREE_MONTHLY_MINUTES_LIMIT
    assert body["monthly_clips_limit"] == usage_service.DEFAULT_FREE_MONTHLY_CLIPS_LIMIT
    assert body["minutes_used_this_period"] == 0
    assert body["clips_used_this_period"] == 0


def test_record_usage_then_summary_reflects_totals(db, test_user):
    """Recording usage and then fetching the summary reflects the recorded minutes/clips."""
    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=5.5, clips_generated=3
    )
    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=2.5, clips_generated=1
    )

    summary = usage_service.get_usage_summary(db, test_user.id)

    assert summary.minutes_used_this_period == 8.0
    assert summary.clips_used_this_period == 4
    assert summary.plan_type == "free"


def test_record_usage_then_summary_via_api(client, db, test_user, auth_headers):
    """The /usage/me endpoint reflects usage recorded through the service layer."""
    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=10.0, clips_generated=4
    )

    response = client.get("/api/v1/usage/me", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["minutes_used_this_period"] == 10.0
    assert body["clips_used_this_period"] == 4


def test_usage_history_returns_records_in_recency_order(db, test_user):
    """get_usage_history returns records most-recent-first."""
    first = usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=1.0, clips_generated=1
    )
    second = usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=2.0, clips_generated=2
    )
    third = usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=3.0, clips_generated=3
    )

    history = usage_service.get_usage_history(db, test_user.id)

    assert [r.id for r in history] == [third.id, second.id, first.id]


def test_usage_history_via_api(client, db, test_user, auth_headers):
    """GET /usage/history returns the user's records, most recent first."""
    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=1.0, clips_generated=1
    )
    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=2.0, clips_generated=2
    )

    response = client.get("/api/v1/usage/history", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["minutes_processed"] == 2.0
    assert body[1]["minutes_processed"] == 1.0


def test_usage_history_respects_skip_and_limit(db, test_user):
    """get_usage_history paginates via skip/limit."""
    for i in range(5):
        usage_service.record_usage(
            db, user_id=test_user.id, project_id=None, minutes_processed=float(i), clips_generated=i
        )

    page = usage_service.get_usage_history(db, test_user.id, skip=1, limit=2)

    assert len(page) == 2


def test_usage_endpoints_require_auth(client):
    """/usage/me and /usage/history reject unauthenticated requests."""
    assert client.get("/api/v1/usage/me").status_code == 401
    assert client.get("/api/v1/usage/history").status_code == 401


def test_check_within_limits(db, test_user):
    """check_within_limits is a read-only comparison, true while under plan limits."""
    assert usage_service.check_within_limits(db, test_user.id) is True

    usage_service.record_usage(
        db, user_id=test_user.id, project_id=None, minutes_processed=1000.0, clips_generated=1
    )

    # Over the free-tier minutes limit, but still just a read-only signal -
    # record_usage above did not raise or block anything.
    assert usage_service.check_within_limits(db, test_user.id) is False
