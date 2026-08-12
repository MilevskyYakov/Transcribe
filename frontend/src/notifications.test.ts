import { describe, expect, it } from "vitest";
import { shouldSendNotifications, terminalNotifications, undeliveredNotifications } from "./notifications";
import type { BatchSession, Job } from "./types";

function job(job_id: string, status: Job["status"]): Job {
  return { job_id, status, source_paths: [], artifacts: {}, metadata: { display_title: job_id }, warnings: [] };
}

describe("terminal notifications", () => {
  it("gates delivery on an inactive managed app", () => {
    expect(shouldSendNotifications(true, false)).toBe(true);
    expect(shouldSendNotifications(true, true)).toBe(false);
    expect(shouldSendNotifications(false, false)).toBe(false);
  });

  it("keeps single jobs separate and aggregates batch success", () => {
    const session: BatchSession = {
      session_id: "batch-1",
      created_at: "2026-08-12T00:00:00Z",
      status: "completed_with_errors",
      totals: { total: 2, configure: 0, processing: 0, ready: 1, failed: 1 },
      items: [
        { item_id: "one", position: 1, source_name: "one.wav", display_title: "One", job_id: "job-1", attempt_job_ids: ["job-1"], status: "ready" },
        { item_id: "two", position: 2, source_name: "two.wav", display_title: "Two", job_id: "job-2", attempt_job_ids: ["job-2"], status: "failed" }
      ]
    };

    const notifications = terminalNotifications(
      [job("single", "completed"), job("job-1", "completed"), job("job-2", "failed")],
      [session]
    );

    expect(notifications.map((notification) => notification.kind)).toEqual([
      "single",
      "batch-failure",
      "batch-summary"
    ]);
    expect(notifications[notifications.length - 1]?.body).toBe("Готово 1 из 2 · Ошибок 1");
  });

  it("deduplicates durable event ids", () => {
    const notifications = terminalNotifications([job("single", "failed")], []);
    expect(undeliveredNotifications(notifications, new Set([notifications[0].id]))).toEqual([]);
  });
});