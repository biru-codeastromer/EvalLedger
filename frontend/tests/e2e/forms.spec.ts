import { expect, test } from "@playwright/test";

const SAMPLE_ARTIFACT = {
  name: "benchmark.jsonl",
  mimeType: "application/json",
  buffer: Buffer.from('{"prompt":"What is provenance?","answer":"Traceability."}\n')
};

test("submit flow only advances when required inputs are present", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "evalledger.session",
      JSON.stringify({
        access_token: "token-123",
        token_type: "bearer",
        user: {
          id: "user-1",
          email: "researcher@example.com",
          username: "researcher",
          is_verified: true,
          is_admin: false
        }
      })
    );
  });

  await page.goto("/submit");

  const stepOneButton = page.getByRole("button", { name: "Continue" });
  await expect(stepOneButton).toBeDisabled();

  await page.getByPlaceholder("Benchmark name").fill("EvalLedger Sample");
  await page.getByPlaceholder("slug").fill("evalledger-sample");
  await page
    .getByPlaceholder("Description")
    .fill("A sample benchmark record used to verify the multi-step submission controls.");
  await expect(stepOneButton).toBeEnabled();

  await stepOneButton.click();
  await expect(page.getByRole("heading", { name: /attach the artifact/i })).toBeVisible();

  const stepTwoButton = page.getByRole("button", { name: "Continue" });
  await expect(stepTwoButton).toBeDisabled();

  await page.getByPlaceholder("Version").fill("1.2.0");
  await page.locator('input[type="file"]').setInputFiles(SAMPLE_ARTIFACT);
  await expect(stepTwoButton).toBeEnabled();

  await stepTwoButton.click();
  await expect(page.getByRole("heading", { name: /review before submission/i })).toBeVisible();
  await expect(page.getByRole("button", { name: "Submit" })).toBeEnabled();
});

test("contamination check stays disabled until a file is selected", async ({ page }) => {
  await page.goto("/contamination");

  const runCheckButton = page.getByRole("button", { name: "Run Check" });
  await expect(runCheckButton).toBeDisabled();

  await page.locator('input[type="file"]').setInputFiles(SAMPLE_ARTIFACT);
  await expect(runCheckButton).toBeEnabled();
});
