import { expect, test, type Page } from "@playwright/test";

const completedJob = {
  job_id: "job-completed",
  source_paths: ["/tmp/Стратегическая встреча.m4a"],
  status: "completed",
  detected_language: "ru",
  artifacts: { final_speech_text_md: "/tmp/final.md" },
  metadata: {
    display_title: "Стратегическая встреча",
    saved_markdown_path: "/Users/demo/Documents/Стратегическая встреча.md",
    saved_markdown_filename: "Стратегическая встреча.md",
    saved_markdown_dir: "/Users/demo/Documents"
  },
  warnings: []
};

async function mockApp(page: Page, jobs: object[]) {
  let batchSessions: any[] = [];
  await page.route("http://127.0.0.1:8765/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("http://127.0.0.1:8765/jobs", (route) => route.fulfill({ json: { jobs } }));
  await page.route("http://127.0.0.1:8765/models", (route) => route.fulfill({
    json: { current_model: "large-v3", models: [{ name: "large-v3", label: "large-v3", status: "ready" }] }
  }));
  await page.route("http://127.0.0.1:8765/batch-sessions", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({ json: { batch_sessions: batchSessions } });
      return;
    }
    const request = route.request().postDataJSON();
    const items = request.items.map((item: any, index: number) => ({
      item_id: `item-${index + 1}`,
      position: index + 1,
      input_path: item.input_path ?? null,
      source_name: item.source_name,
      display_title: item.source_name.replace(/\.[^.]+$/, ""),
      output_dir: "/Users/demo/Documents",
      output_dir_override: null,
      job_id: null,
      attempt_job_ids: [],
      status: "configure",
      job_status: null
    }));
    const session = {
      session_id: "batch-1",
      created_at: "2026-08-11T00:00:00Z",
      common_output_dir: "/Users/demo/Documents",
      status: "active",
      totals: { total: items.length, configure: items.length, processing: 0, ready: 0, failed: 0 },
      items
    };
    batchSessions = [session];
    await route.fulfill({ status: 201, json: { batch_session: session } });
  });
  await page.route(/http:\/\/127\.0\.0\.1:8765\/batch-sessions\/[^/]+\/items\/[^/]+\/submit/, async (route) => {
    const session = batchSessions[0];
    const itemId = route.request().url().split("/").at(-2);
    session.items = session.items.map((item: any) => item.item_id === itemId
      ? { ...item, job_id: "job-batch-1", attempt_job_ids: ["job-batch-1"], status: "processing", job_status: "queued" }
      : item);
    session.totals = { ...session.totals, configure: session.totals.configure - 1, processing: session.totals.processing + 1 };
    jobs.push({ ...completedJob, job_id: "job-batch-1", status: "queued", metadata: { display_title: "one" }, artifacts: {} });
    await route.fulfill({ status: 202, json: { batch_session: session, job: jobs.at(-1) } });
  });
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/transcript/, (route) => route.fulfill({
    json: {
      job: completedJob,
      segments: Array.from({ length: 5 }, (_, index) => ({
        segment_id: String(index + 1),
        start_seconds: index * 8,
        end_seconds: (index + 1) * 8,
        text_raw: `Реплика ${index + 1}`,
        text_clean: `Реплика ${index + 1}`,
        speaker_label: "Яков"
      })),
      words: []
    }
  }));
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/artifacts/, (route) => route.fulfill({ json: { artifacts: [] } }));
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/events/, (route) => route.fulfill({ json: { events: [] } }));
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/final-markdown/, (route) => route.fulfill({ json: { status: "saved", message: "Сохранено", path: "/Users/demo/Documents/Стратегическая встреча.md", filename: "Стратегическая встреча.md" } }));
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/speaker-review/, (route) => route.fulfill({ json: { status: "not_required", groups: [], suggestions: [] } }));
}

test("launch, selected file, history, result and settings keep one workspace state", async ({ page }) => {
  await mockApp(page, [completedJob]);
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Новая транскрипция" })).toBeVisible();
  await expect(page.getByText("Перетащите записи сюда")).toBeVisible();
  await expect(page.getByRole("heading", { name: "История" })).toHaveCount(0);

  await page.getByLabel("Выбрать файл").setInputFiles({ name: "Созвон.m4a", mimeType: "audio/mp4", buffer: Buffer.from("audio") });
  await expect(page.getByText("Созвон.m4a")).toBeVisible();
  await expect(page.getByRole("button", { name: "Начать транскрибацию" })).toBeDisabled();

  await page.getByRole("button", { name: "История", exact: true }).click();
  await expect(page.getByRole("heading", { name: "История" })).toBeVisible();
  await page.getByLabel("Поиск по записям").last().fill("Стратегическая");
  await page.getByRole("button", { name: /Стратегическая встреча/ }).last().click();

  await expect(page.getByRole("heading", { name: "Стратегическая встреча" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Открыть Markdown" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Показать в Finder" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Транскрипция" })).toBeVisible();
  await expect(page.getByText("Реплика 5")).toBeVisible();
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.locator(".transcript-preview")).toHaveCSS("width", "760px");
  await page.setViewportSize({ width: 320, height: 700 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
  await expect(page.getByText("Перетащите записи сюда")).toHaveCount(0);

  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Настройки" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Диагностика" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Автоматизация" })).toHaveCount(0);
});

test("workspace drop accepts media, preserves selection on errors, and hands multiple files to batch", async ({ page }) => {
  await mockApp(page, []);
  await page.goto("/");
  const workspace = page.locator(".workspace");
  const dropFiles = (files: { name: string; type: string }[]) => workspace.evaluate((element, entries) => {
    const transfer = new DataTransfer();
    for (const entry of entries) transfer.items.add(new File(["media"], entry.name, { type: entry.type }));
    element.dispatchEvent(new DragEvent("dragenter", { bubbles: true, dataTransfer: transfer }));
    element.dispatchEvent(new DragEvent("drop", { bubbles: true, dataTransfer: transfer }));
  }, files);

  await dropFiles([{ name: "Первый.m4a", type: "audio/mp4" }]);
  await expect(page.getByText("Первый.m4a")).toBeVisible();

  await dropFiles([{ name: "Второй.mov", type: "video/quicktime" }]);
  await expect(page.getByText("Второй.mov")).toBeVisible();
  await expect(page.getByText("Первый.m4a")).toHaveCount(0);

  await dropFiles([{ name: "notes.txt", type: "text/plain" }]);
  await expect(page.getByText("Второй.mov")).toBeVisible();
  await expect(page.getByText("Этот тип файла не поддерживается. Выберите аудио или видео файл.")).toBeVisible();

  await dropFiles([
    { name: "one.wav", type: "audio/wav" },
    { name: "two.mp3", type: "audio/mpeg" }
  ]);
  await expect(page.getByRole("heading", { name: "Пакет · 1 из 2" })).toBeVisible();
  await expect(page.getByText("one", { exact: true })).toBeVisible();
  await expect(page.locator(".batch-item").filter({ hasText: "two" })).toBeDisabled();
  await page.getByRole("button", { name: "Начать транскрибацию" }).click();
  await expect(page.getByRole("heading", { name: "Пакет · 2 из 2" })).toBeVisible();
  await expect(page.getByText("two", { exact: true })).toBeVisible();
  await expect(page.getByText("Обрабатывается", { exact: true })).toBeVisible();
});

test("processing and error jobs open dedicated states while remaining in history", async ({ page }) => {
  const processing = { ...completedJob, job_id: "job-processing", status: "processing", metadata: { display_title: "Интервью", progress: 68, last_message: "Распознаём речь" }, artifacts: {} };
  const failed = { ...completedJob, job_id: "job-failed", status: "failed", metadata: { display_title: "Сломанная запись", progress: 35 }, warnings: ["[ONNXRuntimeError] raw failure"], artifacts: {} };
  await mockApp(page, [processing, failed]);
  await page.goto("/");

  await page.getByRole("button", { name: /Интервью/ }).click();
  await expect(page.getByText("68%")).toBeVisible();
  await expect(page.getByText("обработка продолжится в фоне", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: /Сломанная запись/ })).toBeVisible();

  await page.getByRole("button", { name: /Сломанная запись/ }).click();
  await expect(page.getByText("Обработка остановилась")).toBeVisible();
  await expect(page.getByRole("button", { name: "Повторить с файлом" })).toBeVisible();
});