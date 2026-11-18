import { ApiError, apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type {
  BacktestConfig,
  BacktestRun,
  DatasetSnapshot,
  ModelCode,
} from "./types";


export function getLatestSnapshot(): Promise<DatasetSnapshot> {
  return apiRequest<DatasetSnapshot>("/api/v1/datasets/snapshots/latest", {
    token: tokenStorage.get(),
  });
}

export type RunFilter = Pick<
  BacktestConfig,
  "dataset_fingerprint" | "horizon_days" | "holdout_days" |
  "min_train_days" | "step_days" | "season_length" | "sarima_maxiter" |
  "m2_n_estimators" | "m2_learning_rate" | "m2_num_leaves" |
  "m2_max_depth" | "m2_min_child_samples" | "m2_seed" |
  "m3_n_estimators" | "m3_learning_rate" | "m3_num_leaves" |
  "m3_max_depth" | "m3_min_child_samples" | "m3_seed"
>;

export async function getLatestRun(
  modelCode: ModelCode,
  filter?: RunFilter,
): Promise<BacktestRun | null> {
  const query = new URLSearchParams({ model_code: modelCode });
  if (filter) {
    query.set("dataset_fingerprint", filter.dataset_fingerprint);
    query.set("horizon_days", String(filter.horizon_days));
    query.set("holdout_days", String(filter.holdout_days));
    query.set("min_train_days", String(filter.min_train_days));
    query.set("step_days", String(filter.step_days));
    if (modelCode === "M0") query.set("season_length", String(filter.season_length));
    if (modelCode === "M1") query.set("sarima_maxiter", String(filter.sarima_maxiter));
    if (modelCode === "M2") {
      query.set("m2_n_estimators", String(filter.m2_n_estimators));
      query.set("m2_learning_rate", String(filter.m2_learning_rate));
      query.set("m2_num_leaves", String(filter.m2_num_leaves));
      query.set("m2_max_depth", String(filter.m2_max_depth));
      query.set("m2_min_child_samples", String(filter.m2_min_child_samples));
      query.set("m2_seed", String(filter.m2_seed));
    }
    if (modelCode === "M3") {
      query.set("m3_n_estimators", String(filter.m3_n_estimators));
      query.set("m3_learning_rate", String(filter.m3_learning_rate));
      query.set("m3_num_leaves", String(filter.m3_num_leaves));
      query.set("m3_max_depth", String(filter.m3_max_depth));
      query.set("m3_min_child_samples", String(filter.m3_min_child_samples));
      query.set("m3_seed", String(filter.m3_seed));
    }
  }
  try {
    return await apiRequest<BacktestRun>(`/api/v1/models/runs/latest?${query}`, {
      token: tokenStorage.get(),
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function runBacktest(config: BacktestConfig): Promise<BacktestRun> {
  return apiRequest<BacktestRun>("/api/v1/models/backtests", {
    method: "POST",
    token: tokenStorage.get(),
    body: JSON.stringify(config),
  });
}

export function getRun(runId: number): Promise<BacktestRun> {
  return apiRequest<BacktestRun>(`/api/v1/models/runs/${runId}`, {
    token: tokenStorage.get(),
  });
}
