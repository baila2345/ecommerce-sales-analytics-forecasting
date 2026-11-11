export type AnalyticsFilters = {
  date_from?: string;
  date_to?: string;
  state?: string;
  category?: string;
  seller_id?: string;
};

export type OverviewMetrics = {
  revenue: number;
  orders: number;
  customers: number;
  average_order_value: number;
  items_sold: number;
  freight_value: number;
  delivered_rate: number;
  average_delivery_days: number | null;
};

export type TrendPoint = { period: string; revenue: number; orders: number };
export type BreakdownPoint = { label: string; value: number; orders: number };
export type ProductPerformance = {
  product_id: string;
  category: string;
  revenue: number;
  units: number;
  orders: number;
};
export type SellerPerformance = {
  seller_id: string;
  location: string;
  revenue: number;
  orders: number;
};
export type RegionPerformance = {
  state: string;
  revenue: number;
  orders: number;
  customers: number;
};
export type DeliveryPerformance = {
  state: string;
  average_days: number;
  on_time_rate: number;
  delivered_orders: number;
};

export type AnalyticsDashboard = {
  filters: AnalyticsFilters;
  overview: OverviewMetrics;
  revenue_trend: TrendPoint[];
  order_statuses: BreakdownPoint[];
  top_categories: BreakdownPoint[];
  top_products: ProductPerformance[];
  top_sellers: SellerPerformance[];
  regions: RegionPerformance[];
  delivery: DeliveryPerformance[];
};

export type AnalyticsFilterOptions = {
  min_date: string | null;
  max_date: string | null;
  states: string[];
  categories: string[];
  sellers: { id: string; label: string }[];
};
