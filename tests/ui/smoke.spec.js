const { test, expect } = require("@playwright/test");

test("@smoke landing page renders core controls", async ({ page }) => {
  await page.goto("/");

  await expect(page).toHaveTitle("Torrent Services Smoke Test");
  await expect(page.getByRole("heading", { name: "Torrent Services" })).toBeVisible();
  await expect(page.getByTestId("status-indicator")).toContainText("Healthy");
  await expect(page.getByRole("button", { name: "Open Dashboard" })).toBeVisible();
});
