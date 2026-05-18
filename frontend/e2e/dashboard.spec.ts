import { expect, test } from "@playwright/test";

test("renders the Russian local dashboard shell", async ({ page }) => {
  await page.route("http://127.0.0.1:8765/health", async (route) => {
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.route("http://127.0.0.1:8765/jobs", async (route) => {
    await route.fulfill({ json: { jobs: [] } });
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Транскрибация" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Запустить", exact: true })).toBeDisabled();
  await expect(page.getByText("Транскрипт пока не готов")).toBeVisible();
  await expect(page.getByText("Диагностика")).toBeVisible();
});
