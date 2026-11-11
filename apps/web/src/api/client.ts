const apiBaseUrl = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type ErrorEnvelope = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
  request_id?: string | null;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details?: unknown,
    public readonly requestId?: string | null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type ApiRequestOptions = RequestInit & {
  token?: string | null;
};

const requestUrl = (path: string) => `${apiBaseUrl}${path}`;

async function errorFromResponse(response: Response): Promise<ApiError> {
  let envelope: ErrorEnvelope = {};
  try {
    envelope = (await response.json()) as ErrorEnvelope;
  } catch {
    // The fallback below keeps infrastructure errors understandable.
  }
  return new ApiError(
    response.status,
    envelope.error?.code ?? "REQUEST_FAILED",
    envelope.error?.message ?? "Không thể hoàn tất yêu cầu. Vui lòng thử lại.",
    envelope.error?.details,
    envelope.request_id,
  );
}

export async function apiRequest<T>(
  path: string,
  options: ApiRequestOptions = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await fetch(requestUrl(path), {
    ...options,
    headers,
  });

  if (!response.ok) {
    throw await errorFromResponse(response);
  }

  return (await response.json()) as T;
}

export async function apiDownload(
  path: string,
  options: ApiRequestOptions = {},
): Promise<Blob> {
  const headers = new Headers(options.headers);
  if (options.token) headers.set("Authorization", `Bearer ${options.token}`);
  const response = await fetch(requestUrl(path), { ...options, headers });
  if (!response.ok) throw await errorFromResponse(response);
  return response.blob();
}
