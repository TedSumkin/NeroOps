import { expect, test } from "@playwright/test";

test("keeps a failed entry across reload and synchronizes it once", async ({ page }) => {
  const pet = {
    id: "c3f50c2f-48bf-4db0-bdbc-a236a2cf1ce0",
    name: "Неро",
    species: "dog",
    breed: "Лабрадор",
    birth_date: null,
  };
  const serverEntries: unknown[] = [];
  let rejectCreates = false;
  let createRequests = 0;

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;

    if (path.endsWith("/bootstrap")) {
      await route.fulfill({
        json: {
          pet,
          entry_types: [],
          recent_entries: serverEntries,
          server_time: new Date().toISOString(),
        },
      });
      return;
    }

    if (path.endsWith("/entries") && request.method() === "POST") {
      createRequests += 1;
      if (rejectCreates) {
        await route.abort("connectionrefused");
        return;
      }
      const entry = request.postDataJSON();
      const serverEntry = {
        ...entry,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        attachments: [],
      };
      if (!serverEntries.some((candidate: any) => candidate.id === entry.id)) {
        serverEntries.push(serverEntry);
      }
      await route.fulfill({ json: serverEntry });
      return;
    }

    if (path.endsWith("/entries") && request.method() === "GET") {
      await route.fulfill({
        json: {
          items: serverEntries,
          total: serverEntries.length,
          limit: 200,
          offset: 0,
        },
      });
      return;
    }

    await route.fulfill({ status: 404, json: { detail: "Not mocked" } });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Неро", exact: true })).toBeVisible();

  rejectCreates = true;
  await page.getByRole("button", { name: "Добавить" }).click();
  await page.getByLabel("Заголовок").fill("Офлайн-наблюдение");
  await page.getByLabel("Заметка").fill("Сохранить даже без сервера");
  await page.getByRole("button", { name: "Записать" }).click();

  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("Офлайн-наблюдение")).toBeVisible();
  await expect(page.getByText("Не отправлено")).toBeVisible();

  await page.reload();
  await page.getByRole("button", { name: "История" }).click();
  await expect(page.getByText("Офлайн-наблюдение")).toBeVisible();
  await expect(page.getByText("Не отправлено")).toBeVisible();

  rejectCreates = false;
  await page.getByRole("button", { name: /в очереди/ }).click();
  await expect(page.getByText("Сохранено")).toBeVisible();
  expect(serverEntries).toHaveLength(1);
  expect(createRequests).toBeGreaterThanOrEqual(3);
});
