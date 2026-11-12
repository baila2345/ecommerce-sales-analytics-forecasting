import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthProvider";
import {
  getLatestM0Run,
  getLatestSnapshot,
  runM0Backtest,
} from "../features/modelLab/api";
import type {
  BacktestConfig,
  BacktestFold,
  BacktestRun,
  DatasetSnapshot,
  PredictionPoint,
} from "../features/modelLab/types";


const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});
const number = new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 });
const dateFormatter = new Intl.DateTimeFormat("vi-VN", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});

function formatDate(value: string): string {
  return dateFormatter.format(new Date(`${value}T00:00:00Z`));
}

function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể tải Model Lab. Vui lòng thử lại.";
}

export function ModelLabPage() {
  const { user } = useAuth();
  const canRun = user?.role === "admin" || user?.role === "analyst";
  const [snapshot, setSnapshot] = useState<DatasetSnapshot | null>(null);
  const [run, setRun] = useState<BacktestRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFoldNo, setSelectedFoldNo] = useState<number | null>(null);
  const [config, setConfig] = useState({
    horizon_days: 30 as 7 | 30,
    holdout_days: 90,
    min_train_days: 365,
    step_days: 30,
    season_length: 7,
  });

  useEffect(() => {
    let active = true;
    Promise.all([getLatestSnapshot(), getLatestM0Run()])
      .then(([snapshotResponse, runResponse]) => {
        if (!active) return;
        setSnapshot(snapshotResponse);
        setRun(runResponse);
        const lastFold = runResponse?.folds[runResponse.folds.length - 1];
        setSelectedFoldNo(lastFold?.fold_no ?? null);
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const selectedFold = useMemo(
    () => run?.folds.find((fold) => fold.fold_no === selectedFoldNo) ?? null,
    [run, selectedFoldNo],
  );

  async function submitBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!snapshot || !canRun) return;
    setRunning(true);
    setError(null);
    const payload: BacktestConfig = {
      model_code: "M0",
      dataset_fingerprint: snapshot.fingerprint,
      ...config,
    };
    try {
      const response = await runM0Backtest(payload);
      setRun(response);
      setSelectedFoldNo(response.folds[response.folds.length - 1]?.fold_no ?? null);
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setRunning(false);
    }
  }

  return (
    <main className="model-lab-page">
      <header className="model-lab-heading">
        <div>
          <p className="section-label">Forecast experimentation</p>
          <h1>Model Lab</h1>
          <p>Backtest M0 Seasonal Naive trên cùng snapshot và fold cố định.</p>
        </div>
        <span className="model-badge"><b>M0</b> Baseline · Seasonal 7 ngày</span>
      </header>

      {error && <div className="analytics-error" role="alert"><span>!</span><div><strong>Không thể hoàn tất yêu cầu</strong><p>{error}</p></div></div>}

      {loading ? <ModelLabLoading /> : snapshot ? (
        <>
          <section className="model-lab-top-grid">
            <form className="model-config-panel" onSubmit={submitBacktest}>
              <div className="model-panel-heading">
                <div><span>Cấu hình thử nghiệm</span><h2>Rolling-origin backtest</h2></div>
                <small>Snapshot #{snapshot.id}</small>
              </div>
              <div className="model-config-grid">
                <label><span>Horizon</span><select value={config.horizon_days} onChange={(event) => setConfig({ ...config, horizon_days: Number(event.target.value) as 7 | 30 })}><option value={7}>7 ngày</option><option value={30}>30 ngày</option></select></label>
                <label><span>Holdout</span><input type="number" min={30} max={180} value={config.holdout_days} onChange={(event) => setConfig({ ...config, holdout_days: Number(event.target.value) })} /></label>
                <label><span>Train tối thiểu</span><input type="number" min={90} max={730} value={config.min_train_days} onChange={(event) => setConfig({ ...config, min_train_days: Number(event.target.value) })} /></label>
                <label><span>Bước dịch</span><input type="number" min={7} max={90} value={config.step_days} onChange={(event) => setConfig({ ...config, step_days: Number(event.target.value) })} /></label>
              </div>
              <div className="model-config-footer">
                <div><span className="status-dot" /><p><strong>{snapshot.rules_version}</strong><small>{snapshot.mature_days} ngày mature · cutoff {formatDate(snapshot.mature_until)}</small></p></div>
                <button className="button button--primary model-run-button" type="submit" disabled={running || !canRun}>
                  {running ? <><span className="spinner spinner--button" /> Đang chạy...</> : "Chạy backtest M0"}
                </button>
              </div>
              {!canRun && <p className="model-permission-note">Vai trò manager chỉ được xem kết quả backtest.</p>}
            </form>

            <article className="model-lineage-panel">
              <div className="model-panel-heading"><div><span>Data lineage</span><h2>Snapshot đang sử dụng</h2></div><small className="ready-pill">Ready</small></div>
              <dl className="lineage-list">
                <div><dt>Fingerprint</dt><dd title={snapshot.fingerprint}>{snapshot.fingerprint}</dd></div>
                <div><dt>Quality policy</dt><dd>{snapshot.quality_policy_version}</dd></div>
                <div><dt>Maturity</dt><dd>{snapshot.maturity_days} ngày</dd></div>
                <div><dt>Daily sales</dt><dd>{number.format(snapshot.daily_sales_days)} ngày</dd></div>
              </dl>
            </article>
          </section>

          {run ? <ModelResults run={run} selectedFold={selectedFold} onSelectFold={setSelectedFoldNo} isCurrentSnapshot={run.dataset_fingerprint === snapshot.fingerprint} /> : <EmptyModelState />}
        </>
      ) : null}
    </main>
  );
}

function ModelResults({ run, selectedFold, onSelectFold, isCurrentSnapshot }: { run: BacktestRun; selectedFold: BacktestFold | null; onSelectFold: (fold: number) => void; isCurrentSnapshot: boolean }) {
  return (
    <>
      {!isCurrentSnapshot && <div className="model-stale-warning">Run này thuộc snapshot cũ. Hãy chạy lại M0 trước khi so sánh model.</div>}
      <section className="model-result-heading">
        <div><p className="section-label">Validation result</p><h2>Kết quả M0 · Run #{run.id}</h2></div>
        <span className="run-status">● {run.status}</span>
      </section>
      <section className="model-kpi-grid">
        <MetricCard label="MAE trung bình" value={currency.format(run.metrics.mae_mean)} note={`± ${currency.format(run.metrics.mae_std)}`} />
        <MetricCard label="RMSE trung bình" value={currency.format(run.metrics.rmse_mean)} note={`± ${currency.format(run.metrics.rmse_std)}`} />
        <MetricCard label="WAPE trung bình" value={run.metrics.wape_mean === null ? "—" : `${number.format(run.metrics.wape_mean)}%`} note={run.metrics.wape_std === null ? "Không đủ mẫu" : `± ${number.format(run.metrics.wape_std)} điểm %`} />
        <MetricCard label="Rolling folds" value={String(run.fold_count)} note={`Horizon ${run.horizon_days} ngày`} />
      </section>
      <div className="holdout-banner"><span>◆</span><div><strong>Holdout đang được khóa</strong><p>{formatDate(run.holdout_from)} – {formatDate(run.holdout_to)} · Chưa dùng để tuning hoặc tính metric.</p></div><b>Chưa đánh giá</b></div>
      <section className="model-detail-grid">
        <article className="analytics-panel model-chart-panel">
          <div className="model-panel-heading"><div><span>Fold diagnostics</span><h2>Actual và prediction</h2></div><small>{selectedFold ? `Fold ${selectedFold.fold_no}` : "Chọn fold"}</small></div>
          {selectedFold ? <PredictionChart points={selectedFold.predictions} /> : null}
        </article>
        <article className="analytics-panel model-fold-panel">
          <div className="model-panel-heading"><div><span>Validation folds</span><h2>Metric theo cửa sổ</h2></div><small>{run.fold_count} fold</small></div>
          <div className="model-table-wrap"><table className="model-fold-table"><thead><tr><th>Fold</th><th>Test range</th><th>MAE</th><th>WAPE</th></tr></thead><tbody>{run.folds.map((fold) => <tr className={selectedFold?.fold_no === fold.fold_no ? "is-selected" : ""} key={fold.fold_no}><td><button type="button" onClick={() => onSelectFold(fold.fold_no)}>#{fold.fold_no}</button></td><td>{formatDate(fold.test_from)} – {formatDate(fold.test_to)}</td><td>{currency.format(fold.metrics.mae)}</td><td>{fold.metrics.wape === null ? "—" : `${number.format(fold.metrics.wape)}%`}</td></tr>)}</tbody></table></div>
        </article>
      </section>
    </>
  );
}

function PredictionChart({ points }: { points: PredictionPoint[] }) {
  if (points.length === 0) {
    return <div className="chart-empty">Fold này chưa có dữ liệu dự báo.</div>;
  }

  const width = 760;
  const height = 260;
  const padding = 28;
  const maxValue = Math.max(...points.flatMap((point) => [point.actual, point.predicted]), 1);
  const x = (index: number) => padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
  const y = (value: number) => height - padding - (value / maxValue) * (height - padding * 2);
  const path = (key: "actual" | "predicted") => points.map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point[key])}`).join(" ");
  return (
    <div className="model-chart-wrap">
      <svg className="model-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Biểu đồ actual và prediction theo ngày">
        {[0.25, 0.5, 0.75].map((ratio) => <line className="chart-grid-line" key={ratio} x1={padding} x2={width - padding} y1={height * ratio} y2={height * ratio} />)}
        <path className="model-chart__actual" d={path("actual")} />
        <path className="model-chart__predicted" d={path("predicted")} />
      </svg>
      <div className="model-chart-legend"><span><i className="legend-actual" />Actual</span><span><i className="legend-predicted" />M0 prediction</span><small>{formatDate(points[0]!.date)} – {formatDate(points[points.length - 1]!.date)}</small></div>
    </div>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="model-kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function EmptyModelState() {
  return <section className="model-empty"><span>M0</span><div><h2>Chưa có backtest</h2><p>Chạy baseline để tạo các fold validation đầu tiên. Holdout 90 ngày vẫn được giữ kín.</p></div></section>;
}

function ModelLabLoading() {
  return <div className="analytics-loading" aria-label="Đang tải Model Lab">{Array.from({ length: 4 }, (_, index) => <span key={index} />)}</div>;
}
