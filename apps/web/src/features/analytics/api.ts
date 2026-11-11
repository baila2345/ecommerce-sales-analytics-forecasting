import { apiDownload, apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type {
  AnalyticsDashboard,
  AnalyticsFilterOptions,
  AnalyticsFilters,
} from "./types";


function queryString(filters: AnalyticsFilters): string {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value) params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function getAnalyticsDashboard(
  filters: AnalyticsFilters,
): Promise<AnalyticsDashboard> {
  return apiRequest<AnalyticsDashboard>(
    `/api/v1/analytics/dashboard${queryString(filters)}`,
    { token: tokenStorage.get() },
  );
}

export function getAnalyticsFilterOptions(): Promise<AnalyticsFilterOptions> {
  return apiRequest<AnalyticsFilterOptions>("/api/v1/analytics/filters", {
    token: tokenStorage.get(),
  });
}

export function exportAnalyticsReport(filters: AnalyticsFilters): Promise<Blob> {
  return apiDownload(`/api/v1/analytics/export${queryString(filters)}`, {
    token: tokenStorage.get(),
  });
}
