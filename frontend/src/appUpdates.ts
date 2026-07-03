import type { DownloadEvent } from "@tauri-apps/plugin-updater";

export type UpdateStatus =
  | "idle"
  | "checking"
  | "not-available"
  | "available"
  | "downloading"
  | "installed"
  | "error";

export interface UpdateState {
  status: UpdateStatus;
  version?: string | null;
  currentVersion?: string | null;
  notes?: string | null;
  downloadedBytes?: number;
  totalBytes?: number | null;
  message: string;
}

export interface PendingUpdate {
  version: string;
  currentVersion: string;
  notes?: string;
  downloadAndInstall: (onEvent?: (event: DownloadEvent) => void) => Promise<void>;
}

export const initialUpdateState: UpdateState = {
  status: "idle",
  message: "Проверить обновления"
};

export function updateStatusTone(status: UpdateStatus): "ok" | "warn" | "error" | "checking" {
  if (status === "available" || status === "installed") return "ok";
  if (status === "error") return "error";
  if (status === "checking" || status === "downloading") return "checking";
  return "warn";
}

export function updateActionLabel(state: UpdateState, isManagedApp: boolean): string {
  if (!isManagedApp) return "Только в приложении";
  if (state.status === "checking") return "Проверяем…";
  if (state.status === "available") return "Установить";
  if (state.status === "downloading") return "Скачиваем…";
  if (state.status === "installed") return "Установлено";
  return "Проверить";
}

export function canRunUpdateAction(state: UpdateState, isManagedApp: boolean): boolean {
  return isManagedApp && !["checking", "downloading", "installed"].includes(state.status);
}

export function updateProgressLabel(state: UpdateState): string | null {
  if (state.status !== "downloading") return null;
  const downloaded = state.downloadedBytes ?? 0;
  const total = state.totalBytes ?? null;
  if (!total) return downloaded > 0 ? `${formatMegabytes(downloaded)} скачано` : "Скачивание началось";
  const percentage = Math.min(100, Math.round((downloaded / total) * 100));
  return `${percentage}% · ${formatMegabytes(downloaded)} из ${formatMegabytes(total)}`;
}

export function updateMessageForError(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error);
  if (isUpdateFeedCheckFailure(error)) {
    return "Канал обновлений пока недоступен. Приложение работает; попробуйте проверить позже.";
  }
  if (detail.toLowerCase().includes("signature")) {
    return "Обновление не установлено: подпись не прошла проверку.";
  }
  return `Не удалось проверить обновление: ${detail}`;
}

export function isReleaseEndpointUnavailable(error: unknown): boolean {
  const detail = error instanceof Error ? error.message : String(error);
  const normalized = detail.toLowerCase();
  return (
    normalized.includes("404") ||
    normalized.includes("not found") ||
    normalized.includes("release not found")
  );
}

export function isUpdateFeedCheckFailure(error: unknown): boolean {
  const detail = error instanceof Error ? error.message : String(error);
  const normalized = detail.toLowerCase();
  return (
    isReleaseEndpointUnavailable(error) ||
    normalized.includes("could not fetch") ||
    normalized.includes("network") ||
    normalized.includes("release endpoint")
  );
}

export async function checkForAppUpdate(): Promise<PendingUpdate | null> {
  const { check } = await import("@tauri-apps/plugin-updater");
  const update = await check();
  if (!update) return null;
  return {
    version: update.version,
    currentVersion: update.currentVersion,
    notes: update.body,
    downloadAndInstall: (onEvent) => update.downloadAndInstall(onEvent)
  };
}

export function reduceDownloadEvent(state: UpdateState, event: DownloadEvent): UpdateState {
  if (event.event === "Started") {
    return {
      ...state,
      status: "downloading",
      downloadedBytes: 0,
      totalBytes: event.data.contentLength ?? null,
      message: "Скачиваю и проверяю подписанное обновление…"
    };
  }
  if (event.event === "Progress") {
    return {
      ...state,
      status: "downloading",
      downloadedBytes: (state.downloadedBytes ?? 0) + event.data.chunkLength,
      message: "Скачиваю и проверяю подписанное обновление…"
    };
  }
  return {
    ...state,
    status: "downloading",
    message: "Загрузка завершена, устанавливаю обновление…"
  };
}

function formatMegabytes(bytes: number): string {
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
