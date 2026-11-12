from app.modules.analytics.cache import AnalyticsCache


class FakeRedis:
    def __init__(self) -> None:
        self.deleted: tuple[str, ...] = ()

    def scan_iter(self, match: str):
        assert match == "analytics:dashboard:v1:*"
        yield "analytics:dashboard:v1:first"
        yield "analytics:dashboard:v1:second"

    def delete(self, *keys: str) -> None:
        self.deleted = keys


def test_dashboard_cache_invalidation_removes_all_dashboard_keys() -> None:
    cache = AnalyticsCache("redis://unused:6379/0")
    fake_redis = FakeRedis()
    cache.client = fake_redis  # type: ignore[assignment]

    cache.invalidate_dashboards()

    assert fake_redis.deleted == (
        "analytics:dashboard:v1:first",
        "analytics:dashboard:v1:second",
    )
