import { expect, test } from "@playwright/test";

test("registry hero headline stays fully inside the banner frame", async ({ page }) => {
  await page.goto("/registry");

  const banner = page.locator('img[alt="Registry hero banner"]').locator("..").locator("..");
  const heading = page.getByRole("heading", {
    name: "Versioned benchmark records with provenance you can cite."
  });

  const bannerBox = await banner.boundingBox();
  const headingBox = await heading.boundingBox();

  expect(bannerBox).not.toBeNull();
  expect(headingBox).not.toBeNull();

  if (!bannerBox || !headingBox) {
    return;
  }

  expect(headingBox.y).toBeGreaterThanOrEqual(bannerBox.y + 8);
  expect(headingBox.y + headingBox.height).toBeLessThanOrEqual(bannerBox.y + bannerBox.height - 8);
});
