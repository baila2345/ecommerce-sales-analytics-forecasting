import { compactCurrency, displayPeriod, numberFormatter } from "../formatters";
import type { BreakdownPoint, TrendPoint } from "../types";


export function EmptyChart() {
  return <div className="chart-empty">Chưa có dữ liệu phù hợp với bộ lọc.</div>;
}

export function RevenueTrendChart({ data }: { data: TrendPoint[] }) {
  if (!data.length) return <EmptyChart />;
  const width = 760;
  const height = 260;
  const padding = 34;
  const max = Math.max(...data.map((point) => point.revenue), 1);
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  const points = data.map((point, index) => {
    const x = padding + (index / Math.max(data.length - 1, 1)) * usableWidth;
    const y = height - padding - (point.revenue / max) * usableHeight;
    return { ...point, x, y };
  });
  const line = points.map((point) => `${point.x},${point.y}`).join(" ");
  const area = `${padding},${height - padding} ${line} ${width - padding},${height - padding}`;

  return (
    <div className="trend-chart-wrap">
      <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Xu hướng doanh thu theo tháng">
        <defs>
          <linearGradient id="revenueArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#2367dd" stopOpacity=".24" />
            <stop offset="100%" stopColor="#2367dd" stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0, .25, .5, .75, 1].map((ratio) => (
          <line key={ratio} x1={padding} x2={width - padding} y1={padding + usableHeight * ratio} y2={padding + usableHeight * ratio} className="chart-grid-line" />
        ))}
        <polygon points={area} fill="url(#revenueArea)" />
        <polyline points={line} className="chart-line" />
        {points.map((point, index) => (
          <g key={point.period}>
            <circle cx={point.x} cy={point.y} r="4" className="chart-dot" />
            {(data.length <= 8 || index % Math.ceil(data.length / 6) === 0 || index === data.length - 1) && (
              <text x={point.x} y={height - 10} textAnchor="middle" className="chart-axis-label">{displayPeriod(point.period)}</text>
            )}
            <title>{`${point.period}: ${compactCurrency(point.revenue)} · ${point.orders} đơn`}</title>
          </g>
        ))}
      </svg>
      <div className="chart-summary-row">
        <span><i className="legend-dot legend-dot--blue" /> Doanh thu</span>
        <strong>Đỉnh: {compactCurrency(max)}</strong>
      </div>
    </div>
  );
}

export function HorizontalBars({
  data,
  valueType = "currency",
}: {
  data: BreakdownPoint[];
  valueType?: "currency" | "number";
}) {
  if (!data.length) return <EmptyChart />;
  const max = Math.max(...data.map((item) => item.value), 1);
  return (
    <div className="horizontal-bars">
      {data.map((item, index) => (
        <div className="bar-row" key={item.label}>
          <span className="bar-rank">{String(index + 1).padStart(2, "0")}</span>
          <div className="bar-copy">
            <div><strong title={item.label}>{item.label}</strong><span>{valueType === "currency" ? compactCurrency(item.value) : numberFormatter.format(item.value)}</span></div>
            <div className="bar-track"><span style={{ width: `${Math.max((item.value / max) * 100, 2)}%` }} /></div>
          </div>
        </div>
      ))}
    </div>
  );
}
