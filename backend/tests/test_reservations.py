"""Route-level tests for the reservation endpoints.

Service-level unit tests (race condition / M4, wish-status / M5) live in
test_security.py. These tests verify the HTTP API contract: correct status
codes, response shapes, and that the owner-privacy rule is enforced at the
route level.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.api.deps.auth import get_current_user
from app.api.deps.database import get_db_session
from app.api.deps.redis import get_redis
from app.core.config import Settings, get_settings
from app.main import create_app


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _settings() -> Settings:
    return Settings(
        telegram_bot_token="test-token",
        jwt_secret_key="test-secret",
        reservation_create_per_hour=100,
        reservation_cancel_per_hour=100,
    )


def _redis_ok() -> AsyncMock:
    """redis mock that passes all rate-limit checks"""
    r = AsyncMock()
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.incr = MagicMock(return_value=pipe)
    pipe.expire = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, True, 1, True])
    r.pipeline = MagicMock(return_value=pipe)
    return r


def _make_app(db: AsyncMock, user: SimpleNamespace, redis: AsyncMock | None = None):
    app = create_app()
    app.dependency_overrides[get_db_session] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_redis] = lambda: (redis or _redis_ok())
    app.dependency_overrides[get_settings] = lambda: _settings()
    return app


def _wish(status: str = "active", owner_id=None) -> MagicMock:
    wish = MagicMock()
    wish.status = status
    wish.wishlist.owner_user_id = owner_id or uuid4()
    wish.wishlist.visibility = "public"
    wish.wishlist_id = uuid4()
    return wish


def _reservation(wish_id, reserver_id, rsv_id=None) -> MagicMock:
    rsv = MagicMock()
    rsv.id = rsv_id or uuid4()
    rsv.wish_id = wish_id
    rsv.reserver_user_id = reserver_id
    rsv.status = "active"
    from datetime import datetime, UTC
    rsv.created_at = datetime.now(UTC)
    rsv.updated_at = datetime.now(UTC)
    return rsv


# ---------------------------------------------------------------------------
# POST /wishes/{wish_id}/reserve
# ---------------------------------------------------------------------------

class TestCreateReservation:
    def test_creates_reservation_returns_201(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        rsv_id = uuid4()
        wish = _wish(owner_id=uuid4())  # user is not owner

        db = AsyncMock()
        # execute calls: (1) _get_accessible_wish, (2) group gift check, (3) FOR UPDATE check
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_existing = AsyncMock()
        no_existing.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_existing, no_existing])
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock(side_effect=lambda r: setattr(r, "id", rsv_id) or setattr(r, "wish_id", wish_id) or setattr(r, "reserver_user_id", user.id) or setattr(r, "status", "active") or None)

        # patch _to_response so we don't need full ORM object
        from datetime import datetime, UTC
        ts = datetime.now(UTC)
        with patch(
            "app.modules.reservations.service._to_response",
            return_value=MagicMock(
                id=rsv_id,
                wish_id=wish_id,
                reserver_user_id=user.id,
                status="active",
                created_at=ts,
                updated_at=ts,
                model_dump=lambda **_: {
                    "id": str(rsv_id),
                    "wish_id": str(wish_id),
                    "reserver_user_id": str(user.id),
                    "status": "active",
                    "created_at": ts.isoformat(),
                    "updated_at": ts.isoformat(),
                },
            ),
        ):
            client = TestClient(_make_app(db, user))
            resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 201

    def test_already_reserved_by_same_user_returns_400(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        wish = _wish(owner_id=uuid4())
        existing = _reservation(wish_id, user.id)  # same reserver

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_group_gift = AsyncMock()
        no_group_gift.scalar_one_or_none = MagicMock(return_value=None)
        existing_result = AsyncMock()
        existing_result.scalar_one_or_none = MagicMock(return_value=existing)
        db.execute = AsyncMock(side_effect=[wish_result, no_group_gift, existing_result])

        client = TestClient(_make_app(db, user))
        resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 400
        assert "Already reserved" in resp.json()["detail"]

    def test_already_reserved_by_other_user_returns_409(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        wish = _wish(owner_id=uuid4())
        existing = _reservation(wish_id, uuid4())  # different reserver

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_group_gift = AsyncMock()
        no_group_gift.scalar_one_or_none = MagicMock(return_value=None)
        existing_result = AsyncMock()
        existing_result.scalar_one_or_none = MagicMock(return_value=existing)
        db.execute = AsyncMock(side_effect=[wish_result, no_group_gift, existing_result])

        client = TestClient(_make_app(db, user))
        resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 409
        assert "already reserved" in resp.json()["detail"].lower()

    def test_race_condition_integrity_error_returns_409(self):
        """concurrent requests: the loser gets 409, not 500"""
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        wish = _wish(owner_id=uuid4())

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_existing = AsyncMock()
        no_existing.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_existing, no_existing])
        db.add = MagicMock()
        db.commit = AsyncMock(side_effect=IntegrityError("uq_reservations_wish_active", {}, None))
        db.rollback = AsyncMock()

        client = TestClient(_make_app(db, user))
        resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 409
        db.rollback.assert_called_once()

    def test_wish_not_found_returns_404(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()

        db = AsyncMock()
        not_found = AsyncMock()
        not_found.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=not_found)

        client = TestClient(_make_app(db, user))
        resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 404

    def test_completed_wish_returns_409(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        wish = _wish(status="completed", owner_id=uuid4())

        db = AsyncMock()
        result = AsyncMock()
        result.scalar_one_or_none = MagicMock(return_value=wish)
        db.execute = AsyncMock(return_value=result)

        client = TestClient(_make_app(db, user))
        resp = client.post(f"/api/v1/wishes/{wish_id}/reserve")

        assert resp.status_code == 409

    def test_unauthenticated_returns_401(self):
        app = create_app()
        app.dependency_overrides[get_db_session] = lambda: AsyncMock()
        app.dependency_overrides[get_redis] = lambda: _redis_ok()
        app.dependency_overrides[get_settings] = lambda: _settings()
        # no get_current_user override — real auth dep fires
        client = TestClient(app)
        resp = client.post(f"/api/v1/wishes/{uuid4()}/reserve")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# DELETE /reservations/{reservation_id}  (reserver cancels)
# ---------------------------------------------------------------------------

class TestCancelReservation:
    def test_cancel_own_reservation_returns_204(self):
        user = SimpleNamespace(id=uuid4())
        rsv_id = uuid4()
        rsv = MagicMock()
        rsv.status = "active"
        rsv.reserver_user_id = user.id

        db = AsyncMock()
        result = AsyncMock()
        result.scalar_one_or_none = MagicMock(return_value=rsv)
        db.execute = AsyncMock(return_value=result)
        db.commit = AsyncMock()

        client = TestClient(_make_app(db, user))
        resp = client.delete(f"/api/v1/reservations/{rsv_id}")

        assert resp.status_code == 204

    def test_cancel_nonexistent_returns_404(self):
        user = SimpleNamespace(id=uuid4())

        db = AsyncMock()
        result = AsyncMock()
        result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(return_value=result)

        client = TestClient(_make_app(db, user))
        resp = client.delete(f"/api/v1/reservations/{uuid4()}")

        assert resp.status_code == 404

    def test_cancel_already_cancelled_returns_400(self):
        user = SimpleNamespace(id=uuid4())
        rsv = MagicMock()
        rsv.status = "cancelled"
        rsv.reserver_user_id = user.id

        db = AsyncMock()
        result = AsyncMock()
        result.scalar_one_or_none = MagicMock(return_value=rsv)
        db.execute = AsyncMock(return_value=result)

        client = TestClient(_make_app(db, user))
        resp = client.delete(f"/api/v1/reservations/{uuid4()}")

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /wishes/{wish_id}/reservation  (owner removes reservation on their wish)
# ---------------------------------------------------------------------------

class TestOwnerCancelReservation:
    def _wish_with_owner(self, owner_id):
        wish = MagicMock()
        wish.id = uuid4()
        wish.wishlist = MagicMock()
        wish.wishlist.owner_user_id = owner_id
        return wish

    def test_owner_can_cancel_reservation(self):
        owner_id = uuid4()
        user = SimpleNamespace(id=owner_id)
        wish_id = uuid4()
        wish = self._wish_with_owner(owner_id)
        rsv = MagicMock()
        rsv.status = "active"

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        rsv_result = AsyncMock()
        rsv_result.scalar_one_or_none = MagicMock(return_value=rsv)
        db.execute = AsyncMock(side_effect=[wish_result, rsv_result])
        db.commit = AsyncMock()

        client = TestClient(_make_app(db, user))
        resp = client.delete(f"/api/v1/wishes/{wish_id}/reservation")

        assert resp.status_code == 204

    def test_non_owner_cannot_cancel_reservation(self):
        owner_id = uuid4()
        other_user = SimpleNamespace(id=uuid4())  # not the owner
        wish_id = uuid4()
        wish = self._wish_with_owner(owner_id)

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        db.execute = AsyncMock(return_value=wish_result)

        client = TestClient(_make_app(db, other_user))
        resp = client.delete(f"/api/v1/wishes/{wish_id}/reservation")

        assert resp.status_code == 403

    def test_owner_cancel_when_no_reservation_returns_404(self):
        owner_id = uuid4()
        user = SimpleNamespace(id=owner_id)
        wish = self._wish_with_owner(owner_id)

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_rsv = AsyncMock()
        no_rsv.scalar_one_or_none = MagicMock(return_value=None)
        no_gift = AsyncMock()
        no_gift.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_gift, no_rsv])

        client = TestClient(_make_app(db, user))
        resp = client.delete(f"/api/v1/wishes/{uuid4()}/reservation")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /wishes/{wish_id}/reservation-status
# ---------------------------------------------------------------------------

class TestReservationStatus:
    def test_unreserved_wish_returns_not_reserved(self):
        user = SimpleNamespace(id=uuid4())
        wish_id = uuid4()
        wish = _wish(owner_id=uuid4())

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        no_rsv = AsyncMock()
        no_rsv.scalar_one_or_none = MagicMock(return_value=None)
        no_gift = AsyncMock()
        no_gift.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_gift, no_rsv])
        db.scalar = AsyncMock(return_value=0)
        db.get = AsyncMock(return_value=SimpleNamespace(group_gift_visibility="anonymous", booking_visibility="anonymous"))

        client = TestClient(_make_app(db, user))
        resp = client.get(f"/api/v1/wishes/{wish_id}/reservation-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_reserved"] is False
        assert data["is_mine"] is False

    def test_reserver_sees_reservation_id(self):
        user_id = uuid4()
        user = SimpleNamespace(id=user_id)
        wish_id = uuid4()
        rsv_id = uuid4()

        wish = _wish(owner_id=uuid4())
        rsv = MagicMock()
        rsv.reserver_user_id = user_id
        rsv.id = rsv_id

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        rsv_result = AsyncMock()
        rsv_result.scalar_one_or_none = MagicMock(return_value=rsv)
        no_gift = AsyncMock()
        no_gift.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_gift, rsv_result])
        db.scalar = AsyncMock(return_value=0)
        db.get = AsyncMock(return_value=SimpleNamespace(group_gift_visibility="anonymous", booking_visibility="anonymous"))

        client = TestClient(_make_app(db, user))
        resp = client.get(f"/api/v1/wishes/{wish_id}/reservation-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_reserved"] is True
        assert data["is_mine"] is True
        assert data["reservation_id"] == str(rsv_id)

    def test_owner_never_sees_reserver_id(self):
        """reservation_id must be None when the wish owner is viewing — privacy invariant"""
        owner_id = uuid4()
        user = SimpleNamespace(id=owner_id, booking_visibility="hidden")
        wish_id = uuid4()

        wish = _wish(owner_id=owner_id)  # user IS the owner
        rsv = MagicMock()
        rsv.reserver_user_id = uuid4()  # someone else reserved it
        rsv.id = uuid4()

        db = AsyncMock()
        wish_result = AsyncMock()
        wish_result.scalar_one_or_none = MagicMock(return_value=wish)
        rsv_result = AsyncMock()
        rsv_result.scalar_one_or_none = MagicMock(return_value=rsv)
        no_gift = AsyncMock()
        no_gift.scalar_one_or_none = MagicMock(return_value=None)
        db.execute = AsyncMock(side_effect=[wish_result, no_gift, rsv_result])
        db.scalar = AsyncMock(return_value=0)

        client = TestClient(_make_app(db, user))
        resp = client.get(f"/api/v1/wishes/{wish_id}/reservation-status")

        assert resp.status_code == 200
        data = resp.json()
        assert data["reservation_id"] is None, (
            "Owner must never receive the reservation_id — privacy invariant violated"
        )
