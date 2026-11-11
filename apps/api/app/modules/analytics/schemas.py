from datetime import date

from pydantic import BaseModel, Field, model_validator


class AnalyticsQuery(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    state: str | None = Field(default=None, min_length=2, max_length=2)
    category: str | None = Field(default=None, max_length=255)
    seller_id: str | None = Field(default=None, max_length=32)

    @model_validator(mode="after")
    def validate_date_range(self) -> "AnalyticsQuery":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        if self.state:
            self.state = self.state.upper()
        return self


class AppliedFilters(BaseModel):
    date_from: date | None
    date_to: date | None
    state: str | None
    category: str | None
    seller_id: str | None


class OverviewMetrics(BaseModel):
    revenue: float
    orders: int
    customers: int
    average_order_value: float
    items_sold: int
    freight_value: float
    delivered_rate: float
    average_delivery_days: float | None


class TrendPoint(BaseModel):
    period: str
    revenue: float
    orders: int


class BreakdownPoint(BaseModel):
    label: str
    value: float
    orders: int


class ProductPerformance(BaseModel):
    product_id: str
    category: str
    revenue: float
    units: int
    orders: int


class SellerPerformance(BaseModel):
    seller_id: str
    location: str
    revenue: float
    orders: int


class RegionPerformance(BaseModel):
    state: str
    revenue: float
    orders: int
    customers: int


class DeliveryPerformance(BaseModel):
    state: str
    average_days: float
    on_time_rate: float
    delivered_orders: int


class SellerOption(BaseModel):
    id: str
    label: str


class FilterOptions(BaseModel):
    min_date: date | None
    max_date: date | None
    states: list[str]
    categories: list[str]
    sellers: list[SellerOption]


class AnalyticsDashboardResponse(BaseModel):
    filters: AppliedFilters
    overview: OverviewMetrics
    revenue_trend: list[TrendPoint]
    order_statuses: list[BreakdownPoint]
    top_categories: list[BreakdownPoint]
    top_products: list[ProductPerformance]
    top_sellers: list[SellerPerformance]
    regions: list[RegionPerformance]
    delivery: list[DeliveryPerformance]
