import { ApiError, apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type {
  BacktestConfig,
  BacktestRun,
  DatasetSnapshot,
} from "./types";


export function getLatestSnapshot(): Promise<DatasetSnapshot> {
  return apiRequest<DatasetSnapshot>("/api/v1/datasets/snapshots/latest", {
    token: tokenStorage.get(),
  });
}

export async function getLatestM0Run(): Promise<BacktestRun | null> {
  try {
    return await apiRequest<BacktestRun>("/api/v1/models/runs/latest", {
      token: tokenStorage.get(),
    });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function runM0Backtest(config: BacktestConfig): Promise<BacktestRun> {
  return apiRequest<BacktestRun>("/api/v1/models/backtests", {
    method: "POST",
    token: tokenStorage.get(),
    body: JSON.stringify(config),
  });
}
