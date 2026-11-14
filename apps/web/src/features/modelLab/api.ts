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

export async function getLatestRun(modelCode: ModelCode): Promise<BacktestRun | null> {
  try {
    return await apiRequest<BacktestRun>(`/api/v1/models/runs/latest?model_code=${modelCode}`, {
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
