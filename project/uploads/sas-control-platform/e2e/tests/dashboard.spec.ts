import { expect, test } from "@playwright/test";

// These run against a live stack (docker compose up). They exercise the
// safety-critical surfaces: the simulation banner must always be present, the
// fleet must render, and a hazardous action must demand confirmation.

test.describe("Overview dashboard", () => {
  test("shows the simulation banner and fleet KPIs", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText(/SIMULATION MODE/i)).toBeVisible();
    await expect(page.getByText("Units", { exact: true })).toBeVisible();
    await expect(page.getByText("Online", { exact: true })).toBeVisible();
    // racks render with at least one unit tile
    await expect(page.getByText(/units ·/i).first()).toBeVisible();
  });

  test("navigates to a simulator console", async ({ page }) => {
    await page.goto("/devices");
    await expect(page.getByText("Simulator Control")).toBeVisible();
    const firstUnit = page.locator("a[href^='/devices/']").first();
    await firstUnit.click();
    await expect(page).toHaveURL(/\/devices\/.+/);
    await expect(page.getByText("Telemetry")).toBeVisible();
    await expect(page.getByText(/Voltage/i).first()).toBeVisible();
  });
});

test.describe("Safety flows", () => {
  test("enabling output requires confirmation", async ({ page }) => {
    await page.goto("/devices");
    await page.locator("a[href^='/devices/']").first().click();
    await expect(page.getByText("Output & shutdown")).toBeVisible();

    const enable = page.getByRole("button", { name: /^Enable$/ });
    if (await enable.isEnabled()) {
      await enable.click();
      // a confirmation dialog must appear before anything is energised
      await expect(page.getByRole("button", { name: /Enable output/i })).toBeVisible();
      await page.getByRole("button", { name: /Cancel/i }).click();
    }
  });

  test("safe shutdown demands a typed confirmation phrase", async ({ page }) => {
    await page.goto("/devices");
    await page.locator("a[href^='/devices/']").first().click();
    const shutdown = page.getByRole("button", { name: /Safe shutdown/i });
    await shutdown.click();
    const execute = page.getByRole("button", { name: /Execute shutdown/i });
    await expect(execute).toBeDisabled();
    await page.getByRole("textbox").last().fill("SHUTDOWN");
    await expect(execute).toBeEnabled();
    await page.getByRole("button", { name: /Cancel/i }).click();
  });
});

test.describe("Scenario builder", () => {
  test("loads the example scenario on a canvas", async ({ page }) => {
    await page.goto("/scenarios/builder");
    await expect(page.getByText("Node palette")).toBeVisible();
    await expect(page.getByRole("button", { name: /Validate/i })).toBeVisible();
    // the seeded example scenario renders Start/End nodes
    await expect(page.locator(".react-flow__node").first()).toBeVisible();
  });
});
