"""
测试长期偏好仓储与服务。
"""

from app.domain.contracts import UserProfile
from app.repositories.sqlite_profile_repository import SqliteProfileRepository
from app.services.profile_service import ProfileService


def test_profile_repository_round_trip(tmp_path):
    repo = SqliteProfileRepository(tmp_path / "runs.sqlite3")
    repo.init_schema()
    service = ProfileService(repo)

    client_id = "browser-a"
    empty_profile = service.get_profile(client_id)
    assert empty_profile.updated_at is None
    assert empty_profile.profile.model_dump() == UserProfile().model_dump()

    saved = service.update_profile(
        client_id,
        UserProfile(
            capital_amount=50000,
            currency="usd",
            risk_tolerance="Low",
            investment_horizon="Long-term",
            investment_style="Dividend",
            preferred_sectors=["Healthcare", "Healthcare", "Consumer Defensive"],
            preferred_industries=["Drug Manufacturers - General"],
        ),
    )

    assert saved.updated_at is not None
    assert saved.profile.currency == "USD"
    assert saved.profile.preferred_sectors == ["Healthcare", "Consumer Defensive"]

    loaded = service.get_profile(client_id)
    assert loaded.profile.capital_amount == 50000
    assert loaded.profile.investment_style == "Dividend"
    assert loaded.profile.preferred_industries == ["Drug Manufacturers - General"]

    cleared = service.clear_profile(client_id)
    assert cleared.updated_at is None
    assert cleared.profile.model_dump() == UserProfile().model_dump()
