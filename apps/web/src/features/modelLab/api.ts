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
  "min_train_days" | "step_days" | "season_length" | "sarima_maxiter"
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
    query.set(
      modelCode === "M0" ? "season_length" : "sarima_maxiter",
      String(modelCode === "M0" ? filter.season_length : filter.sarima_maxiter),
    );
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
