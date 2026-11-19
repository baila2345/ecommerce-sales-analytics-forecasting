export type DatasetSnapshot = {
  id: number;
  fingerprint: string;
  status: "building" | "ready" | "failed" | "stale";
  source_checksums: Record<string, string>;
  rules_version: string;
  quality_policy_version: string;
  source_timezone: string;
  maturity_days: number;
  source_min_date: string;
  source_max_date: string;
  mature_until: string;
  daily_sales_days: number;
  mature_days: number;
  sales_value: number;
  orders_count: number;
  customer_days: number;
  items_count: number;
  created_at: string;
  completed_at: string | null;
};

export type ModelCode = "M0" | "M1" | "M2" | "M3" | "M4";
export type RunStatus = "queued" | "running" | "succeeded" | "failed";

export type BacktestConfig = {
  model_code: ModelCode;
  dataset_fingerprint: string;
  horizon_days: 7 | 30;
  holdout_days: number;
  min_train_days: number;
  step_days: number;
  season_length: number;
  sarima_order: [number, number, number];
  sarima_seasonal_order: [number, number, number, number];
  sarima_maxiter: number;
  m2_n_estimators: number;
  m2_learning_rate: number;
  m2_num_leaves: number;
  m2_max_depth: number;
  m2_min_child_samples: number;
  m2_seed: number;
  m3_n_estimators: number;
  m3_learning_rate: number;
  m3_num_leaves: number;
  m3_max_depth: number;
  m3_min_child_samples: number;
  m3_seed: number;
  m4_alpha_grid: number[];
};

export type PredictionPoint = {
  date: string;
  actual: number;
  predicted: number;
  predicted_orders?: number | null;
  predicted_aov?: number | null;
  actual_orders?: number | null;
  actual_aov?: number | null;
  predicted_m2?: number | null;
  predicted_m3?: number | null;
  ensemble_alpha?: number | null;
};

export type FoldMetrics = {
  mae: number;
  rmse: number;
  wape: number | null;
  actual_sum: number;
  prediction_sum: number;
};

export type BacktestFold = {
  fold_no: number;
  origin_date: string;
  train_from: string;
  train_to: string;
  test_from: string;
  test_to: string;
  metrics: FoldMetrics;
  predictions: PredictionPoint[];
};

export type BacktestRun = {
  id: number;
  model_code: ModelCode;
  status: RunStatus;
  dataset_fingerprint: string;
  snapshot_id: number;
  horizon_days: number;
  holdout_days: number;
  min_train_days: number;
  step_days: number;
  experiment_key: string | null;
  model_version: string | null;
  feature_schema_hash: string | null;
  selected_alpha: number | null;
  alpha_grid: number[] | null;
  holdout_from: string;
  holdout_to: string;
  holdout_evaluated: boolean;
  fold_count: number;
  metrics: {
    mae_mean: number;
    mae_std: number;
    rmse_mean: number;
    rmse_std: number;
    wape_mean: number | null;
    wape_std: number | null;
  } | null;
  component_metrics: {
    orders_mae: number;
    orders_wape: number;
    aov_mae: number;
    aov_wape: number;
  } | null;
  folds: BacktestFold[];
  job_id: string | null;
  error: {
    code: string;
    message: string;
    stage?: string;
    fold_no?: number | null;
    error_type?: string;
  } | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};
