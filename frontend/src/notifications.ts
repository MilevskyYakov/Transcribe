import type { BatchSession, Job } from "./types";

const STORAGE_KEY = "mnema-delivered-notifications";
const INITIALIZED_KEY = "mnema-notifications-initialized";

type NotificationKind = "single" | "batch-failure" | "batch-summary";

export interface AppNotification {
  body: string;
  id: string;
  kind: NotificationKind;
  title: string;
}

export function undeliveredNotifications(
  notifications: AppNotification[],
  delivered: Set<string>
): AppNotification[] {
  return notifications.filter((notification) => !delivered.has(notification.id));
}

export function shouldSendNotifications(isManagedApp: boolean, isFocused: boolean): boolean {
  return isManagedApp && !isFocused;
}

export function terminalNotifications(jobs: Job[], sessions: BatchSession[]): AppNotification[] {
  const batchJobIds = new Set(sessions.flatMap((session) => session.items.flatMap((item) => item.attempt_job_ids)));
  const notifications: AppNotification[] = [];

  for (const job of jobs) {
    if (batchJobIds.has(job.job_id)) continue;
    if (["completed", "completed_with_warnings"].includes(job.status)) {
      notifications.push({
        id: `job:${job.job_id}:completed`,
        kind: "single",
        title: "Транскрипция готова",
        body: String(job.metadata.display_title ?? job.metadata.title ?? job.metadata.source_filename ?? job.job_id)
      });
    } else if (["failed", "failed_partial"].includes(job.status)) {
      notifications.push({
        id: `job:${job.job_id}:failed`,
        kind: "single",
        title: "Ошибка транскрипции",
        body: String(job.metadata.display_title ?? job.metadata.title ?? job.metadata.source_filename ?? job.job_id)
      });
    }
  }

  for (const session of sessions) {
    for (const item of session.items.filter((candidate) => candidate.status === "failed")) {
      notifications.push({
        id: `batch:${session.session_id}:item:${item.item_id}:job:${item.job_id ?? "unknown"}:failed`,
        kind: "batch-failure",
        title: "Ошибка в пакете",
        body: item.display_title
      });
    }
    if (session.status !== "active") {
      notifications.push({
        id: `batch:${session.session_id}:summary`,
        kind: "batch-summary",
        title: session.status === "completed" ? "Пакет готов" : "Пакет завершён с ошибками",
        body: `Готово ${session.totals.ready} из ${session.totals.total}${session.totals.failed ? ` · Ошибок ${session.totals.failed}` : ""}`
      });
    }
  }

  return notifications;
}

function deliveredIds(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

function storeDeliveredIds(ids: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
}

export async function requestNotificationPermission(): Promise<boolean> {
  try {
    const { isPermissionGranted, requestPermission } = await import("@tauri-apps/plugin-notification");
    return await isPermissionGranted() || await requestPermission() === "granted";
  } catch {
    return false;
  }
}

export async function deliverTerminalNotifications(
  jobs: Job[],
  sessions: BatchSession[],
  isManagedApp: boolean
): Promise<void> {
  if (!isManagedApp) return;
  const delivered = deliveredIds();
  const pending = undeliveredNotifications(terminalNotifications(jobs, sessions), delivered);

  if (localStorage.getItem(INITIALIZED_KEY) !== "true") {
    for (const notification of pending) delivered.add(notification.id);
    storeDeliveredIds(delivered);
    localStorage.setItem(INITIALIZED_KEY, "true");
    return;
  }
  if (!pending.length) return;

  let focused = true;
  try {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    focused = await getCurrentWindow().isFocused();
  } catch {
    return;
  }

  if (shouldSendNotifications(isManagedApp, focused)) {
    try {
      const { isPermissionGranted, sendNotification } = await import("@tauri-apps/plugin-notification");
      if (await isPermissionGranted()) {
        for (const notification of pending) sendNotification({ title: notification.title, body: notification.body });
      }
    } catch {
      // Notification failure must never affect transcription or polling.
    }
  }

  for (const notification of pending) delivered.add(notification.id);
  storeDeliveredIds(delivered);
}
