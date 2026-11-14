import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../features/auth/AuthProvider";
import {
  getLatestRun,
  getLatestSnapshot,
  getRun,
  runBacktest,
} from "../features/modelLab/api";
import type {
  BacktestConfig,
  BacktestFold,
  BacktestRun,
  DatasetSnapshot,
  ModelCode,
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
const terminalStatuses = new Set(["succeeded", "failed"]);

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
  const [runs, setRuns] = useState<Partial<Record<ModelCode, BacktestRun>>>({});
  const [modelCode, setModelCode] = useState<ModelCode>("M0");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFoldNo, setSelectedFoldNo] = useState<number | null>(null);
  const [config, setConfig] = useState({
    horizon_days: 30 as 7 | 30,
    holdout_days: 90,
    min_train_days: 365,
    step_days: 30,
    season_length: 7,
    sarima_maxiter: 100,
  });

  useEffect(() => {
    let active = true;
    Promise.all([
      getLatestSnapshot(),
      getLatestRun("M0"),
      getLatestRun("M1"),
    ])
      .then(([snapshotResponse, m0, m1]) => {
        if (!active) return;
        setSnapshot(snapshotResponse);
        setRuns({ ...(m0 ? { M0: m0 } : {}), ...(m1 ? { M1: m1 } : {}) });
      })
      .catch((requestError) => {
        if (active) setError(errorMessage(requestError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const activeRun = runs[modelCode] ?? null;
  const pendingRun = Object.values(runs).find(
    (run) => run && !terminalStatuses.has(run.status),
  );

  useEffect(() => {
    if (!pendingRun) return;
    let active = true;
    const poll = window.setInterval(() => {
      getRun(pendingRun.id)
        .then((response) => {
          if (!active) return;
          setRuns((current) => ({ ...current, [response.model_code]: response }));
          if (terminalStatuses.has(response.status)) window.clearInterval(poll);
        })
        .catch((requestError) => {
          if (active) setError(errorMessage(requestError));
          window.clearInterval(poll);
        });
    }, 1200);
    return () => {
      active = false;
      window.clearInterval(poll);
    };
  }, [pendingRun?.id]);

  useEffect(() => {
    const lastFold = activeRun?.folds[activeRun.folds.length - 1];
    setSelectedFoldNo(lastFold?.fold_no ?? null);
  }, [activeRun?.id, activeRun?.status]);

  const selectedFold = useMemo(
    () => activeRun?.folds.find((fold) => fold.fold_no === selectedFoldNo) ?? null,
    [activeRun, selectedFoldNo],
  );

  async function submitBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!snapshot || !canRun || pendingRun) return;
    setSubmitting(true);
    setError(null);
    const payload: BacktestConfig = {
      model_code: modelCode,
      dataset_fingerprint: snapshot.fingerprint,
      ...config,
      sarima_order: [1, 1, 1],
      sarima_seasonal_order: [1, 0, 1, 7],
    };
    try {
      const response = await runBacktest(payload);
      setRuns((current) => ({ ...current, [response.model_code]: response }));
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="model-lab-page">
      <header className="model-lab-heading">
        <div>
          <p className="section-label">Forecast experimentation</p>
          <h1>Model Lab</h1>
          <p>Backtest M0 và M1 trên cùng snapshot, fold và holdout cố định.</p>
        </div>
        <span className="model-badge"><b>{modelCode}</b> {modelCode === "M0" ? "Seasonal Naive" : "SARIMA (1,1,1) × (1,0,1,7)"}</span>
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
              <div className="model-config-grid model-config-grid--models">
                <label><span>Model</span><select value={modelCode} onChange={(event) => setModelCode(event.target.value as ModelCode)}><option value="M0">M0 · Seasonal Naive</option><option value="M1">M1 · SARIMA</option></select></label>
                <label><span>Horizon</span><select value={config.horizon_days} onChange={(event) => setConfig({ ...config, horizon_days: Number(event.target.value) as 7 | 30 })}><option value={7}>7 ngày</option><option value={30}>30 ngày</option></select></label>
                <label><span>Holdout</span><input type="number" min={30} max={180} value={config.holdout_days} onChange={(event) => setConfig({ ...config, holdout_days: Number(event.target.value) })} /></label>
                <label><span>Train tối thiểu</span><input type="number" min={90} max={730} value={config.min_train_days} onChange={(event) => setConfig({ ...config, min_train_days: Number(event.target.value) })} /></label>
                <label><span>Bước dịch</span><input type="number" min={7} max={90} value={config.step_days} onChange={(event) => setConfig({ ...config, step_days: Number(event.target.value) })} /></label>
                {modelCode === "M1" && <label><span>SARIMA max iterations</span><input type="number" min={10} max={500} value={config.sarima_maxiter} onChange={(event) => setConfig({ ...config, sarima_maxiter: Number(event.target.value) })} /></label>}
              </div>
              {modelCode === "M1" && <p className="model-config-note">M1 dùng order (1,1,1), seasonal order (1,0,1,7). Mỗi fold chỉ fit dữ liệu trước origin.</p>}
              <div className="model-config-footer">
                <div><span className="status-dot" /><p><strong>{snapshot.rules_version}</strong><small>{snapshot.mature_days} ngày mature · cutoff {formatDate(snapshot.mature_until)}</small></p></div>
                <button className="button button--primary model-run-button" type="submit" disabled={submitting || Boolean(pendingRun) || !canRun}>
                  {submitting ? <><span className="spinner spinner--button" /> Đang xếp hàng...</> : pendingRun ? `${pendingRun.model_code} đang ${pendingRun.status}` : `Chạy backtest ${modelCode}`}
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

          <ModelComparison runs={runs} activeModel={modelCode} onSelect={setModelCode} />
          {activeRun ? <ModelResults run={activeRun} selectedFold={selectedFold} onSelectFold={setSelectedFoldNo} isCurrentSnapshot={activeRun.dataset_fingerprint === snapshot.fingerprint} /> : <EmptyModelState modelCode={modelCode} />}
        </>
      ) : null}
    </main>
  );
}

function ModelComparison({ runs, activeModel, onSelect }: { runs: Partial<Record<ModelCode, BacktestRun>>; activeModel: ModelCode; onSelect: (model: ModelCode) => void }) {
  if (!runs.M0 && !runs.M1) return null;
  return (
    <section className="analytics-panel model-comparison-panel">
      <div className="model-panel-heading"><div><span>Leaderboard</span><h2>So sánh trên validation</h2></div><small>Cùng fingerprint mới có ý nghĩa</small></div>
      <div className="model-table-wrap"><table className="model-fold-table model-comparison-table"><thead><tr><th>Model</th><th>Trạng thái</th><th>MAE</th><th>RMSE</th><th>WAPE</th><th>Folds</th></tr></thead><tbody>{(["M0", "M1"] as ModelCode[]).map((code) => { const run = runs[code]; return <tr className={activeModel === code ? "is-selected" : ""} key={code}><td><button type="button" onClick={() => onSelect(code)}>{code}</button></td><td><RunState status={run?.status ?? "—"} /></td><td>{run?.metrics ? currency.format(run.metrics.mae_mean) : "—"}</td><td>{run?.metrics ? currency.format(run.metrics.rmse_mean) : "—"}</td><td>{run?.metrics?.wape_mean == null ? "—" : `${number.format(run.metrics.wape_mean)}%`}</td><td>{run?.fold_count ?? "—"}</td></tr>; })}</tbody></table></div>
    </section>
  );
}

function RunState({ status }: { status: string }) {
  return <span className={`run-state run-state--${status}`}>{status}</span>;
}

function ModelResults({ run, selectedFold, onSelectFold, isCurrentSnapshot }: { run: BacktestRun; selectedFold: BacktestFold | null; onSelectFold: (fold: number) => void; isCurrentSnapshot: boolean }) {
  if (run.status === "queued" || run.status === "running") return <RunProgress run={run} />;
  if (run.status === "failed") return <RunFailure run={run} />;
  if (!run.metrics) return null;
  return (
    <>
      {!isCurrentSnapshot && <div className="model-stale-warning">Run này thuộc snapshot cũ. Hãy chạy lại {run.model_code} trước khi so sánh model.</div>}
      <section className="model-result-heading">
        <div><p className="section-label">Validation result</p><h2>Kết quả {run.model_code} · Run #{run.id}</h2></div>
        <RunState status={run.status} />
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
          {selectedFold ? <PredictionChart points={selectedFold.predictions} modelCode={run.model_code} /> : null}
        </article>
        <article className="analytics-panel model-fold-panel">
          <div className="model-panel-heading"><div><span>Validation folds</span><h2>Metric theo cửa sổ</h2></div><small>{run.fold_count} fold</small></div>
          <div className="model-table-wrap"><table className="model-fold-table"><thead><tr><th>Fold</th><th>Test range</th><th>MAE</th><th>WAPE</th></tr></thead><tbody>{run.folds.map((fold) => <tr className={selectedFold?.fold_no === fold.fold_no ? "is-selected" : ""} key={fold.fold_no}><td><button type="button" onClick={() => onSelectFold(fold.fold_no)}>#{fold.fold_no}</button></td><td>{formatDate(fold.test_from)} – {formatDate(fold.test_to)}</td><td>{currency.format(fold.metrics.mae)}</td><td>{fold.metrics.wape === null ? "—" : `${number.format(fold.metrics.wape)}%`}</td></tr>)}</tbody></table></div>
        </article>
      </section>
    </>
  );
}

function RunProgress({ run }: { run: BacktestRun }) {
  return <section className="model-run-progress" aria-live="polite"><span className="spinner" /><div><h2>{run.model_code} đang {run.status === "queued" ? "chờ worker" : "chạy backtest"}</h2><p>Run #{run.id} · Giao diện tự cập nhật khi worker hoàn tất.</p></div><RunState status={run.status} /></section>;
}

function RunFailure({ run }: { run: BacktestRun }) {
  const fold = run.error?.fold_no ? ` tại fold #${run.error.fold_no}` : "";
  return <section className="model-run-failure" role="alert"><span>!</span><div><h2>{run.model_code} chạy thất bại{fold}</h2><p>{run.error?.message ?? "Worker không thể hoàn tất backtest."}</p></div><RunState status="failed" /></section>;
}

function PredictionChart({ points, modelCode }: { points: PredictionPoint[]; modelCode: ModelCode }) {
  if (points.length === 0) return <div className="chart-empty">Fold này chưa có dữ liệu dự báo.</div>;
  const width = 760;
  const height = 260;
  const padding = 28;
  const maxValue = Math.max(...points.flatMap((point) => [point.actual, point.predicted]), 1);
  const x = (index: number) => padding + (index / Math.max(points.length - 1, 1)) * (width - padding * 2);
  const y = (value: number) => height - padding - (value / maxValue) * (height - padding * 2);
  const path = (key: "actual" | "predicted") => points.map((point, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(point[key])}`).join(" ");
  return <div className="model-chart-wrap"><svg className="model-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Biểu đồ actual và prediction theo ngày">{[0.25, 0.5, 0.75].map((ratio) => <line className="chart-grid-line" key={ratio} x1={padding} x2={width - padding} y1={height * ratio} y2={height * ratio} />)}<path className="model-chart__actual" d={path("actual")} /><path className="model-chart__predicted" d={path("predicted")} /></svg><div className="model-chart-legend"><span><i className="legend-actual" />Actual</span><span><i className="legend-predicted" />{modelCode} prediction</span><small>{formatDate(points[0]!.date)} – {formatDate(points[points.length - 1]!.date)}</small></div></div>;
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return <article className="model-kpi"><span>{label}</span><strong>{value}</strong><small>{note}</small></article>;
}

function EmptyModelState({ modelCode }: { modelCode: ModelCode }) {
  return <section className="model-empty"><span>{modelCode}</span><div><h2>Chưa có backtest {modelCode}</h2><p>Chạy model để tạo các fold validation. Holdout 90 ngày vẫn được giữ kín.</p></div></section>;
}

function ModelLabLoading() {
  return <div className="analytics-loading" aria-label="Đang tải Model Lab">{Array.from({ length: 4 }, (_, index) => <span key={index} />)}</div>;
}
