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

test("signed-in administrators see account and review navigation", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "evalledger.session",
      JSON.stringify({
        access_token: "token-123",
        token_type: "bearer",
        user: {
          id: "user-1",
          email: "admin@example.com",
          username: "admin",
          is_verified: true,
          is_admin: true
        }
      })
    );
  });

  await page.goto("/");
  await expect(page.getByRole("link", { name: "Account" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Review" })).toBeVisible();
});

test("footer exposes the exact repository link", async ({ page }) => {
  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();
  const githubLink = page.getByRole("link", { name: "GitHub" });
  await expect(githubLink).toHaveAttribute("href", "https://github.com/biru-codeastromer/EvalLedger");
});

test("footer policy links land on live product pages", async ({ page }) => {
  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();

  await page.locator("footer a[href='/privacy']").first().click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { name: "Privacy" })).toBeVisible();

  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();
  await page.locator("footer a[href='/terms']").first().click();
  await expect(page).toHaveURL(/\/terms$/);
  await expect(page.getByRole("heading", { name: /terms of service/i })).toBeVisible();

  await page.goto("/");
  await page.locator("footer").scrollIntoViewIfNeeded();
  await page.locator("footer a[href='/acceptable-use']").first().click();
  await expect(page).toHaveURL(/\/acceptable-use$/);
  await expect(page.getByRole("heading", { name: /acceptable use/i })).toBeVisible();
});
