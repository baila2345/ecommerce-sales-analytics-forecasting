import { apiDownload, apiRequest } from "../../api/client";
import { tokenStorage } from "../auth/storage";
import type {
  AnalyticsDashboard,
  AnalyticsFilterOptions,
  AnalyticsFilters,
} from "./types";


const dashboardRequests = new Map<string, Promise<AnalyticsDashboard>>();
let filterOptionsRequest: Promise<AnalyticsFilterOptions> | null = null;


function clearDashboardRequest(
  path: string,
  request: Promise<AnalyticsDashboard>,
): void {
  if (dashboardRequests.get(path) === request) dashboardRequests.delete(path);
}


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
  const path = `/api/v1/analytics/dashboard${queryString(filters)}`;
  const pending = dashboardRequests.get(path);
  if (pending) return pending;

  const request = apiRequest<AnalyticsDashboard>(
    path,
    { token: tokenStorage.get() },
  );
  dashboardRequests.set(path, request);
  request.then(
    () => clearDashboardRequest(path, request),
    () => clearDashboardRequest(path, request),
  );
  return request;
}

export function getAnalyticsFilterOptions(): Promise<AnalyticsFilterOptions> {
  if (filterOptionsRequest) return filterOptionsRequest;

  const request = apiRequest<AnalyticsFilterOptions>("/api/v1/analytics/filters", {
    token: tokenStorage.get(),
  });
  filterOptionsRequest = request;
  request.then(
    () => { if (filterOptionsRequest === request) filterOptionsRequest = null; },
    () => { if (filterOptionsRequest === request) filterOptionsRequest = null; },
  );
  return request;
}

export function exportAnalyticsReport(filters: AnalyticsFilters): Promise<Blob> {
  return apiDownload(`/api/v1/analytics/export${queryString(filters)}`, {
    token: tokenStorage.get(),
  });
}
