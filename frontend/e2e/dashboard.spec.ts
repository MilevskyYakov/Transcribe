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
  await page.route("http://127.0.0.1:8765/health", (route) => route.fulfill({ json: { status: "ok" } }));
  await page.route("http://127.0.0.1:8765/jobs", (route) => route.fulfill({ json: { jobs } }));
  await page.route("http://127.0.0.1:8765/models", (route) => route.fulfill({
    json: { current_model: "large-v3", models: [{ name: "large-v3", label: "large-v3", status: "ready" }] }
  }));
  await page.route(/http:\/\/127\.0\.0\.1:8765\/jobs\/[^/]+\/transcript/, (route) => route.fulfill({
    json: { job: completedJob, segments: [{ segment_id: "1", start_seconds: 0, end_seconds: 8, text_raw: "Обсудили план запуска.", text_clean: "Обсудили план запуска.", speaker_label: "Яков" }], words: [] }
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
  await expect(page.getByText("Фрагмент транскрипции")).toBeVisible();
  await expect(page.getByText("Перетащите записи сюда")).toHaveCount(0);

  await page.getByRole("button", { name: "Настройки", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Настройки" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Диагностика" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Автоматизация" })).toBeVisible();
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