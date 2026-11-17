import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
const token = readFileSync(
  path.resolve("../outputs/local-access-token.txt"),
  "utf8",
).trim();
test("Operator journey: zone, approved policy, demo, action, analytics, export", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("로컬 접근 토큰").fill(token);
  await page.getByRole("button", { name: "콘솔 연결" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Buildings / Zones", exact: true })
    .click();
  await page.getByLabel("공간 이름").fill("E2E test zone " + Date.now());
  await page.getByRole("button", { name: "공간 등록", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("공간을 등록");
  await page.getByRole("button", { name: "Policies", exact: true }).click();
  await page.getByLabel("미식별·범위 밖 fallback ε (선택)").fill("1");
  await page.getByRole("button", { name: "검토용 초안 저장" }).click();
  await page.getByRole("button", { name: "이 정책 승인" }).last().click();
  await expect(
    page.getByText("APPROVED", { exact: true }).last(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Operation", exact: true }).click();
  await page.getByLabel("승인 정책").selectOption({ index: 1 });
  await page.getByRole("button", { name: "가상 데이터 생성" }).click();
  await expect(page.getByRole("status")).toContainText("가상 관측");
  await page.getByRole("button", { name: "권고 온도 계산" }).click();
  await expect(
    page.getByRole("heading", { name: "권고 검토 · 아직 적용되지 않음" }),
  ).toBeVisible();
  await page.getByLabel("처리 근거").fill("E2E simulated approval");
  await page.getByRole("button", { name: "승인", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("승인을 저장");
  await page.screenshot({
    path: "../validation/OPERATION.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Analytics", exact: true }).click();
  await page.getByRole("button", { name: "분석 조회" }).click();
  await expect(
    page.getByText("Asia/Seoul · DEMO", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Elicitation", exact: true }).click();
  await page.getByRole("button", { name: "새 세션 만들기" }).click();
  await expect(page.getByRole("button", { name: "결과 확인" })).toBeVisible();
  await page.getByRole("button", { name: "결과 확인" }).click();
  await expect(
    page.getByRole("heading", { name: "COMMON · 공통 ε 비교 기준" }),
  ).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "기록 내보내기" }).click();
  expect((await download).suggestedFilename()).toMatch(/npsdm-.*zip/);
  await page.screenshot({
    path: "../validation/ELICITATION.png",
    fullPage: true,
  });
});
test("Invalid credentials remain blocked", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("로컬 접근 토큰").fill("invalid");
  await page.getByRole("button", { name: "콘솔 연결" }).click();
  await expect(page.locator(".error[role=alert]")).toContainText(
    "Valid bearer token required",
  );
});
