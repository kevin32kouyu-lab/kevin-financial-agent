import type {
  DataStatus,
  DeleteRunsResponse,
  HistoryFilters,
  RunArtifactsResponse,
  RunCreateRequest,
  RunDetailResponse,
  RunEvent,
  RunListResponse,
  RuntimeConfig,
} from "./types";

const EVENT_TYPES = [
  "run.created",
  "run.started",
  "run.resumed",
  "artifact.updated",
  "step.completed",
  "run.completed",
  "run.failed",
  "run.needs_clarification",
];

async function requestJson<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      // Handle different error formats:
      // 1. FastAPI validation error: { detail: [...errors] }
      // 2. Our global exception: { error: "string" } or { error: {...} }
      // 3. Normal: { detail: "string" }
      if (body.detail) {
        if (Array.isArray(body.detail)) {
          // Multiple validation errors: join all messages
          detail = body.detail.map((err: any) => err.msg || JSON.stringify(err)).join(', ');
        } else if (typeof body.detail === 'string') {
          detail = body.detail;
        } else {
          // detail is an object
          detail = JSON.stringify(body.detail);
        }
      } else if (body.error) {
        if (typeof body.error === 'string') {
          detail = body.error;
        } else {
          // error is an object, extract message if available
          detail = body.error.message || JSON.stringify(body.error);
        }
      }
    } catch {
      const text = await response.text();
      detail = text || detail;
    }
    throw new Error(detail || "请求失败");
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}

export function listRuns(filters: HistoryFilters, limit = 20) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (filters.search.trim()) {
    params.set("search", filters.search.trim());
  }
  if (filters.mode.trim()) {
    params.set("mode", filters.mode.trim());
  }
  if (filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  return requestJson<RunListResponse>(`/api/runs?${params.toString()}`);
}

export function getRunDetail(runId: string) {
  return requestJson<RunDetailResponse>(`/api/runs/${runId}`);
}

export function getRunArtifacts(runId: string) {
  return requestJson<RunArtifactsResponse>(`/api/runs/${runId}/artifacts`);
}

export function createRun(payload: RunCreateRequest) {
  return requestJson<RunDetailResponse>("/api/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function retryRun(runId: string) {
  return requestJson<RunDetailResponse>(`/api/runs/${runId}/retry`, {
    method: "POST",
  });
}

export function clearRuns(filters: HistoryFilters) {
  const params = new URLSearchParams();
  if (filters.search.trim()) {
    params.set("search", filters.search.trim());
  }
  if (filters.mode.trim()) {
    params.set("mode", filters.mode.trim());
  }
  if (filters.status.trim()) {
    params.set("status", filters.status.trim());
  }
  const query = params.toString();
  return requestJson<DeleteRunsResponse>(`/api/runs${query ? `?${query}` : ""}`, {
    method: "DELETE",
  });
}

export function getRuntimeConfig() {
  return requestJson<RuntimeConfig>("/api/v1/agent/runtime-config");
}

export function getDataStatus() {
  return requestJson<DataStatus>("/api/v1/data/status");
}

export function refreshDataStatus() {
  return requestJson<DataStatus>("/api/v1/data/refresh", {
    method: "POST",
  });
}

export function openRunEventStream(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onError: () => void,
): EventSource {
  const source = new EventSource(`/api/runs/${runId}/events`);

  const handle = (event: MessageEvent<string>) => {
    try {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      onEvent({
        id: event.lastEventId ? Number(event.lastEventId) : undefined,
        event_type: event.type || "message",
        payload,
      });
    } catch {
      onEvent({
        id: event.lastEventId ? Number(event.lastEventId) : undefined,
        event_type: event.type || "message",
        payload: { raw: event.data },
      });
    }
  };

  source.onmessage = handle;
  EVENT_TYPES.forEach((eventType) => {
    source.addEventListener(eventType, handle as EventListener);
  });
  source.onerror = () => {
    onError();
  };
  return source;
}
