import { currencyFormatter, numberFormatter } from "../formatters";
import type {
  DeliveryPerformance,
  ProductPerformance,
  RegionPerformance,
  SellerPerformance,
} from "../types";


export function ProductTable({ rows }: { rows: ProductPerformance[] }) {
  return (
    <AnalyticsTable headers={["Sản phẩm", "Danh mục", "Đã bán", "Doanh thu"]} empty={!rows.length}>
      {rows.map((row) => (
        <tr key={row.product_id}>
          <td><code>{row.product_id.slice(0, 10)}…</code></td>
          <td>{row.category}</td>
          <td>{numberFormatter.format(row.units)}</td>
          <td><strong>{currencyFormatter.format(row.revenue)}</strong></td>
        </tr>
      ))}
    </AnalyticsTable>
  );
}

export function SellerTable({ rows }: { rows: SellerPerformance[] }) {
  return (
    <AnalyticsTable headers={["Seller", "Khu vực", "Đơn hàng", "Doanh thu"]} empty={!rows.length}>
      {rows.map((row) => (
        <tr key={row.seller_id}>
          <td><code>{row.seller_id.slice(0, 10)}…</code></td>
          <td>{row.location}</td>
          <td>{numberFormatter.format(row.orders)}</td>
          <td><strong>{currencyFormatter.format(row.revenue)}</strong></td>
        </tr>
      ))}
    </AnalyticsTable>
  );
}

export function RegionTable({ rows }: { rows: RegionPerformance[] }) {
  return (
    <AnalyticsTable headers={["Bang", "Khách hàng", "Đơn hàng", "Doanh thu"]} empty={!rows.length}>
      {rows.map((row) => (
        <tr key={row.state}>
          <td><span className="state-pill">{row.state}</span></td>
          <td>{numberFormatter.format(row.customers)}</td>
          <td>{numberFormatter.format(row.orders)}</td>
          <td><strong>{currencyFormatter.format(row.revenue)}</strong></td>
        </tr>
      ))}
    </AnalyticsTable>
  );
}

export function DeliveryTable({ rows }: { rows: DeliveryPerformance[] }) {
  return (
    <AnalyticsTable headers={["Bang", "Đơn đã giao", "Giao TB", "Đúng hạn"]} empty={!rows.length}>
      {rows.map((row) => (
        <tr key={row.state}>
          <td><span className="state-pill">{row.state}</span></td>
          <td>{numberFormatter.format(row.delivered_orders)}</td>
          <td>{row.average_days} ngày</td>
          <td><strong className={row.on_time_rate >= 90 ? "text-success" : ""}>{row.on_time_rate}%</strong></td>
        </tr>
      ))}
    </AnalyticsTable>
  );
}

function AnalyticsTable({
  headers,
  empty,
  children,
}: {
  headers: string[];
  empty: boolean;
  children: React.ReactNode;
}) {
  if (empty) return <div className="chart-empty">Chưa có dữ liệu phù hợp với bộ lọc.</div>;
  return (
    <div className="analytics-table-wrap">
      <table className="analytics-table">
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
