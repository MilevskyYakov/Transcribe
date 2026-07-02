import { expect, test } from "@playwright/test";

test("renders the Russian local dashboard shell", async ({ page }) => {
  await page.route("http://127.0.0.1:8765/health", async (route) => {
    await route.fulfill({ json: { status: "ok" } });
  });
  await page.route("http://127.0.0.1:8765/jobs", async (route) => {
    await route.fulfill({ json: { jobs: [] } });
  });
  await page.route("http://127.0.0.1:8765/models", async (route) => {
    await route.fulfill({
      json: {
        current_model: "large-v3",
        models: [{ name: "large-v3", label: "large-v3", status: "ready" }]
      }
    });
  });

  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Транскрибация" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Запустить транскрибацию", exact: true })).toBeDisabled();
  await expect(page.getByText("Здесь появится готовая расшифровка")).toBeVisible();
  await expect(page.getByText("Файл", { exact: true })).toBeVisible();
});
