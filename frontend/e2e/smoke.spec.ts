import { expect, test } from "@playwright/test";

test("la carte indique l'absence de données puis affiche la démonstration étiquetée", async ({ page }) => {
  await page.goto("/carte");
  await expect(page.getByText("Aucune acquisition NISAR n'est disponible")).toBeVisible();
  await page.getByLabel("Afficher les données de démonstration simulées").check();
  await expect(page.getByRole("alert").filter({ hasText: "DONNÉES DE DÉMONSTRATION SIMULÉES" })).toBeVisible();
  await expect(page.getByTestId("timeline-date")).not.toHaveText("-");
  await expect(page.getByText("6 dates réelles")).toBeVisible();
});

test("le traducteur affiche les classes et l'avertissement prototype", async ({ page }) => {
  await page.goto("/traducteur");
  await page.getByLabel("Données de démonstration simulées").check();
  await expect(page.getByLabel("Légende des classes")).toBeVisible();
  await expect(page.getByText(/non validé/i).first()).toBeVisible();
  await expect(page.getByRole("list", { name: undefined }).getByText(/Végétation dense/).first()).toBeVisible();
  await page.getByRole("tab", { name: "Changements" }).click();
  await expect(page.getByLabel("Résumé des changements")).toContainText("Surface modifiée");
});

test("le récit de démonstration montre le bandeau simulé", async ({ page }) => {
  await page.goto("/recits/demo-defrichement");
  await expect(page.getByRole("heading", { name: /défrichement simulé/i })).toBeVisible();
  await expect(page.getByText("DONNÉES SIMULÉES. Pas une observation NISAR.")).toBeVisible();
});

test("niveau 1 : simulateur et quiz validé par le serveur", async ({ page }) => {
  await page.goto("/apprendre");
  await page.getByRole("link", { name: "Commencer" }).first().click();
  await expect(page.getByText("Simulation conceptuelle")).toBeVisible();
  const groups = page.locator("fieldset");
  const n = await groups.count();
  for (let i = 0; i < n; i++) await groups.nth(i).getByRole("radio").first().check();
  await page.getByRole("button", { name: "Valider mes réponses" }).click();
  await expect(page.getByText(/bonne\(s\) réponse\(s\) sur/)).toBeVisible();
});

test("tableau de bord : série temporelle sur une zone, puis export CSV", async ({ page }) => {
  await page.goto("/tableau-de-bord");
  await page.getByLabel("Inclure les données de démonstration simulées").check();
  await page.getByRole("button", { name: "Créer la zone" }).click();
  await expect(page.getByText(/Zone active/)).toBeVisible();
  const block = page.getByLabel("Série temporelle", { exact: true });
  await block.getByRole("button", { name: "Lancer l'analyse" }).click();
  await expect(block.getByRole("img", { name: /Moyenne du signal HH et HV/ })).toBeVisible();
  const [dl] = await Promise.all([page.waitForEvent("download"), block.getByRole("button", { name: "CSV" }).click()]);
  expect(dl.suggestedFilename()).toContain(".csv");
});
