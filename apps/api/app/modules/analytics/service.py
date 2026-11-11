import csv
from io import StringIO

from app.modules.analytics.cache import AnalyticsCache
from app.modules.analytics.filters import AnalyticsFilters
from app.modules.analytics.repository import AnalyticsRepository
from app.modules.analytics.schemas import (
    AnalyticsDashboardResponse,
    AnalyticsQuery,
    AppliedFilters,
    FilterOptions,
)


class AnalyticsService:
    def __init__(
        self,
        repository: AnalyticsRepository,
        cache: AnalyticsCache | None = None,
    ) -> None:
        self.repository = repository
        self.cache = cache

    @staticmethod
    def _filters(query: AnalyticsQuery) -> AnalyticsFilters:
        return AnalyticsFilters(**query.model_dump())

    def dashboard(self, query: AnalyticsQuery) -> AnalyticsDashboardResponse:
        query_json = query.model_dump_json()
        cache_key = self.cache.dashboard_key(query_json) if self.cache else None
        if self.cache and cache_key:
            cached = self.cache.get(cache_key)
            if cached:
                return AnalyticsDashboardResponse.model_validate_json(cached)

        filters = self._filters(query)
        dashboard = AnalyticsDashboardResponse(
            filters=AppliedFilters(**query.model_dump()),
            overview=self.repository.overview(filters),
            revenue_trend=self.repository.revenue_trend(filters),
            order_statuses=self.repository.order_statuses(filters),
            top_categories=self.repository.top_categories(filters),
            top_products=self.repository.top_products(filters),
            top_sellers=self.repository.top_sellers(filters),
            regions=self.repository.regions(filters),
            delivery=self.repository.delivery(filters),
        )
        if self.cache and cache_key:
            self.cache.set(cache_key, dashboard.model_dump_json(), ttl_seconds=60)
        return dashboard

    def filter_options(self) -> FilterOptions:
        return FilterOptions(**self.repository.filter_options())

    def export_csv(self, query: AnalyticsQuery) -> str:
        dashboard = self.dashboard(query)
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Salescope Analytics Report"])
        writer.writerow(["Metric", "Value"])
        for key, value in dashboard.overview.model_dump().items():
            writer.writerow([key, value if value is not None else ""])
        writer.writerow([])
        writer.writerow(["Revenue trend"])
        writer.writerow(["Period", "Revenue", "Orders"])
        for point in dashboard.revenue_trend:
            writer.writerow([point.period, point.revenue, point.orders])
        writer.writerow([])
        writer.writerow(["Order statuses"])
        writer.writerow(["Status", "Orders"])
        for point in dashboard.order_statuses:
            writer.writerow([point.label, point.orders])
        writer.writerow([])
        writer.writerow(["Top categories"])
        writer.writerow(["Category", "Revenue", "Orders"])
        for point in dashboard.top_categories:
            writer.writerow([point.label, point.value, point.orders])
        writer.writerow([])
        writer.writerow(["Top products"])
        writer.writerow(["Product ID", "Category", "Revenue", "Units", "Orders"])
        for product in dashboard.top_products:
            writer.writerow(
                [
                    product.product_id,
                    product.category,
                    product.revenue,
                    product.units,
                    product.orders,
                ]
            )
        writer.writerow([])
        writer.writerow(["Top sellers"])
        writer.writerow(["Seller ID", "Location", "Revenue", "Orders"])
        for seller in dashboard.top_sellers:
            writer.writerow(
                [seller.seller_id, seller.location, seller.revenue, seller.orders]
            )
        writer.writerow([])
        writer.writerow(["Customer regions"])
        writer.writerow(["State", "Revenue", "Orders", "Customers"])
        for region in dashboard.regions:
            writer.writerow(
                [region.state, region.revenue, region.orders, region.customers]
            )
        writer.writerow([])
        writer.writerow(["Delivery performance"])
        writer.writerow(["State", "Average days", "On-time rate", "Orders"])
        for delivery in dashboard.delivery:
            writer.writerow(
                [
                    delivery.state,
                    delivery.average_days,
                    delivery.on_time_rate,
                    delivery.delivered_orders,
                ]
            )
        return "\ufeff" + output.getvalue()
