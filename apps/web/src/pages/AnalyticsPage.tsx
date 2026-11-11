import { useEffect, useState } from "react";

import { ApiError } from "../api/client";
import { HorizontalBars, RevenueTrendChart } from "../features/analytics/components/AnalyticsCharts";
import { AnalyticsFilters as FilterBar } from "../features/analytics/components/AnalyticsFilters";
import {
  DeliveryTable,
  ProductTable,
  RegionTable,
  SellerTable,
} from "../features/analytics/components/AnalyticsTables";
import {
  exportAnalyticsReport,
  getAnalyticsDashboard,
  getAnalyticsFilterOptions,
} from "../features/analytics/api";
import {
  compactCurrency,
  currencyFormatter,
  numberFormatter,
} from "../features/analytics/formatters";
import type {
  AnalyticsDashboard,
  AnalyticsFilterOptions,
  AnalyticsFilters as FilterValues,
} from "../features/analytics/types";


const emptyFilters: FilterValues = {};

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể tải dữ liệu phân tích. Vui lòng thử lại.";
}

export function AnalyticsPage() {
  const [options, setOptions] = useState<AnalyticsFilterOptions | null>(null);
  const [draftFilters, setDraftFilters] = useState<FilterValues>(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState<FilterValues>(emptyFilters);
  const [dashboard, setDashboard] = useState<AnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getAnalyticsFilterOptions()
      .then((response) => {
        if (active) setOptions(response);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    getAnalyticsDashboard(appliedFilters)
      .then((response) => {
        if (active) setDashboard(response);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [appliedFilters]);

  function applyFilters() {
    setAppliedFilters({ ...draftFilters });
  }

  function resetFilters() {
    setDraftFilters(emptyFilters);
    setAppliedFilters(emptyFilters);
  }

  async function exportReport() {
    setExporting(true);
    setError(null);
    try {
      const blob = await exportAnalyticsReport(appliedFilters);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "salescope-analytics.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setExporting(false);
    }
  }

  const metrics = dashboard?.overview;

  return (
    <main className="analytics-page">
      <header className="analytics-heading">
        <div>
          <p className="section-label">Business Intelligence</p>
          <h1>Analytics Dashboard</h1>
          <p>Hiệu suất bán hàng, khách hàng và vận hành từ dữ liệu Olist.</p>
        </div>
        <div className="analytics-heading__status">
          <span aria-hidden="true" />
          <div><strong>Nguồn dữ liệu Olist</strong><small>Đơn delivered · BRL</small></div>
        </div>
      </header>

      <FilterBar
        filters={draftFilters}
        options={options}
        busy={loading || exporting}
        onChange={setDraftFilters}
        onApply={applyFilters}
        onReset={resetFilters}
        onExport={exportReport}
      />

      {error && (
        <div className="analytics-error" role="alert">
          <span aria-hidden="true">!</span><div><strong>Không thể cập nhật báo cáo</strong><p>{error}</p></div>
        </div>
      )}

      {loading && !dashboard ? (
        <AnalyticsLoading />
      ) : dashboard && metrics ? (
        <>
          <section className="analytics-kpi-grid" aria-label="Chỉ số kinh doanh">
            <KpiCard label="Doanh thu" value={currencyFormatter.format(metrics.revenue)} note={`${numberFormatter.format(metrics.items_sold)} sản phẩm đã bán`} icon="R$" tone="blue" />
            <KpiCard label="Đơn đã giao" value={numberFormatter.format(metrics.orders)} note={`${metrics.delivered_rate}% tổng đơn`} icon="✓" tone="green" />
            <KpiCard label="Khách hàng" value={numberFormatter.format(metrics.customers)} note="Theo customer unique ID" icon="◉" tone="violet" />
            <KpiCard label="Giá trị đơn TB" value={currencyFormatter.format(metrics.average_order_value)} note="Doanh thu / đơn đã giao" icon="↗" tone="amber" />
            <KpiCard label="Phí vận chuyển" value={compactCurrency(metrics.freight_value)} note="Tổng freight value" icon="⌁" tone="slate" />
            <KpiCard label="Thời gian giao TB" value={metrics.average_delivery_days === null ? "—" : `${metrics.average_delivery_days} ngày`} note="Từ lúc đặt đến lúc nhận" icon="◷" tone="cyan" />
          </section>

          <section className="analytics-chart-grid">
            <article className="analytics-panel analytics-panel--wide">
              <PanelHeading eyebrow="Xu hướng" title="Doanh thu theo tháng" meta={`${dashboard.revenue_trend.length} kỳ`} />
              <RevenueTrendChart data={dashboard.revenue_trend} />
            </article>
            <article className="analytics-panel">
              <PanelHeading eyebrow="Đơn hàng" title="Trạng thái đơn" meta={`${numberFormatter.format(dashboard.order_statuses.reduce((sum, item) => sum + item.orders, 0))} đơn`} />
              <HorizontalBars data={dashboard.order_statuses} valueType="number" />
            </article>
          </section>

          <section className="analytics-chart-grid analytics-chart-grid--equal">
            <article className="analytics-panel">
              <PanelHeading eyebrow="Sản phẩm" title="Danh mục dẫn đầu" meta="Theo doanh thu" />
              <HorizontalBars data={dashboard.top_categories} />
            </article>
            <article className="analytics-panel">
              <PanelHeading eyebrow="Địa lý" title="Doanh thu theo bang" meta="Top 10" />
              <HorizontalBars data={dashboard.regions.map((region) => ({ label: region.state, value: region.revenue, orders: region.orders }))} />
            </article>
          </section>

          <section className="analytics-detail-grid">
            <article className="analytics-panel">
              <PanelHeading eyebrow="Product performance" title="Sản phẩm nổi bật" meta="Top 8" />
              <ProductTable rows={dashboard.top_products} />
            </article>
            <article className="analytics-panel">
              <PanelHeading eyebrow="Seller performance" title="Seller nổi bật" meta="Top 8" />
              <SellerTable rows={dashboard.top_sellers} />
            </article>
            <article className="analytics-panel">
              <PanelHeading eyebrow="Customer geography" title="Thị trường theo khu vực" meta="Top 10" />
              <RegionTable rows={dashboard.regions} />
            </article>
            <article className="analytics-panel">
              <PanelHeading eyebrow="Delivery performance" title="Hiệu suất giao hàng" meta="Top 10 bang" />
              <DeliveryTable rows={dashboard.delivery} />
            </article>
          </section>
        </>
      ) : null}
    </main>
  );
}

function KpiCard({ label, value, note, icon, tone }: { label: string; value: string; note: string; icon: string; tone: string }) {
  return (
    <article className="analytics-kpi">
      <div><span>{label}</span><strong>{value}</strong><small>{note}</small></div>
      <span className={`analytics-kpi__icon analytics-kpi__icon--${tone}`}>{icon}</span>
    </article>
  );
}

function PanelHeading({ eyebrow, title, meta }: { eyebrow: string; title: string; meta: string }) {
  return (
    <div className="analytics-panel__heading">
      <div><span>{eyebrow}</span><h2>{title}</h2></div><small>{meta}</small>
    </div>
  );
}

function AnalyticsLoading() {
  return (
    <div className="analytics-loading" aria-label="Đang tải dữ liệu">
      {Array.from({ length: 6 }, (_, index) => <span key={index} />)}
    </div>
  );
}
