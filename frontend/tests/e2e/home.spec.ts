import { test, expect } from "@playwright/test";

test("homepage renders hero", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /open registry/i })).toBeVisible();
});

