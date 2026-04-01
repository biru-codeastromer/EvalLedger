import { expect, test } from "@playwright/test";

test("top-level navigation lands on working destinations", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("link", { name: "Docs" }).click();
  await expect(page).toHaveURL(/\/docs$/);
  await expect(page.getByRole("heading", { name: /read the registry/i })).toBeVisible();

  await page.getByRole("link", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: /sign in to manage submissions/i })).toBeVisible();

  await page.getByRole("link", { name: "Submit Benchmark" }).click();
  await expect(page).toHaveURL(/\/submit$/);
  await expect(page.getByRole("heading", { name: /register a benchmark/i })).toBeVisible();
});

test("footer exposes the exact repository link", async ({ page }) => {
  await page.goto("/");
  const githubLink = page.getByRole("link", { name: "GitHub" });
  await expect(githubLink).toHaveAttribute("href", "https://github.com/biru-codeastromer/EvalLedger");
});
