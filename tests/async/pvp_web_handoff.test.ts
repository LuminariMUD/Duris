/** Copied beside DurisWeb's service tests for the disposable paired journey. */
import { afterAll, beforeAll, expect, it, jest } from "@jest/globals";
import mysql, { type Pool } from "mysql2/promise";
import express from "express";
import request from "supertest";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

let pool: Pool;
const settings = { pvpDelayMinutes: 0, respectWebinfoToggle: true };
jest.unstable_mockModule("../../db/connection.js", () => ({
  pool: {
    query: (sql: string, params?: unknown[]) => pool.query(sql, params),
    getConnection: () => pool.getConnection(),
  },
}));
jest.unstable_mockModule("../webSettingsService.js", () => ({
  getWebSettings: async () => settings,
}));
jest.unstable_mockModule("../../middleware/auth.js", () => ({
  requireAuth: (_req: unknown, _res: unknown, next: () => void) => next(),
  optionalAuth: (_req: unknown, _res: unknown, next: () => void) => next(),
}));
jest.unstable_mockModule("../../utils/logger.js", () => ({
  default: { error: jest.fn() },
  isErrorWithCode: () => false,
}));
jest.unstable_mockModule("../../config/environment.js", () => ({
  getBackendConfiguration: () => ({ environment: "test" }),
}));
const service = await import("../pvpService.js");
const { default: routes } = await import("../../routes/pvp.js");
const { errorHandler } = await import("../../middleware/errorHandler.js");
const app = express();
app.use(express.json());
app.use("/api/pvp", routes);
app.use(errorHandler);
const directory = process.env.PVP_CAPTURE_COMMAND_DIR!;
const events: number[] = JSON.parse(readFileSync(join(directory, "events.json"), "utf8"));
let originalConsent: unknown;
beforeAll(async () => {
  const port = Number(process.env.TEST_PVP_DB_PORT);
  if (!Number.isInteger(port) || port < 1024 || [3306, 3307].includes(port))
    throw Error("Disposable port required");
  pool = mysql.createPool({
    host: "127.0.0.1",
    port,
    user: "pvp",
    password: "pvp-fixture",
    database: "duris_test",
    dateStrings: true,
    connectionLimit: 2,
  });
  await pool.query("SET time_zone='+00:00'");
  for (const statement of [
    "CREATE TABLE IF NOT EXISTS pvp_battle_favorites(event_id INT, account_name VARCHAR(255), created_at DATETIME DEFAULT CURRENT_TIMESTAMP)",
    "CREATE TABLE IF NOT EXISTS pvp_battle_likes(event_id INT, account_name VARCHAR(255), UNIQUE(event_id, account_name))",
    "CREATE TABLE IF NOT EXISTS pvp_battle_comments(id INT PRIMARY KEY AUTO_INCREMENT, event_id INT, account_name VARCHAR(255), character_pid INT, content TEXT, parent_id INT, is_deleted INT DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, quoted_text TEXT, line_number INT, participant_id INT)",
  ])
    await pool.query(statement);
  await pool.query("DELETE FROM pvp_battle_comments");
  await pool.query("UPDATE pkill_event SET comment_count=0 WHERE id IN (?)", [events]);
  [originalConsent] = await pool.query(
    "SELECT event_id,pid,webinfo_at_capture,equip,log FROM pkill_info WHERE pid IN (100,101) ORDER BY id",
  );
});
afterAll(async () => {
  if (pool) await pool.end();
});

it("publishes real MUD captures through anonymous routes, gates quotes and renders both viewports", async () => {
  async function detail(event: number) {
    const response = await request(app).get(`/api/pvp/events/${event}`);
    expect(response.status).toBe(200);
    expect(response.headers["cache-control"]).toBe("no-store");
    expect(response.body.participants).toHaveLength(2);
    expect(JSON.stringify(response.body)).not.toMatch(/PRIVATE_HANDOFF_MARKER|OFF_INTERVAL/);
    return response.body;
  }
  async function matrix(expected: string[][]) {
    for (let i = 0; i < events.length; i++) {
      const data = await detail(events[i]);
      const participants = [...data.participants].sort((a, b) => a.pid - b.pid);
      expect(participants.map((p) => p.pov_status)).toEqual(expected[i]);
      for (const p of participants) {
        if (p.pov_status !== "public") {
          expect(p.log).toBeNull();
          expect(p.equip).toBeNull();
        } else {
          expect(p.equip).toBe("EQUIPMENT_FIXTURE\r\n");
          if (i === 3) expect(p.log).toBe("");
          else expect(p.log).toContain(p.pid === 100 ? "PUBLIC_A_LINE" : "PUBLIC_B_LINE");
        }
      }
    }
  }
  const permitted = [
    ["public", "private"],
    ["public", "public"],
    ["private", "private"],
    ["public", "public"],
    ["unavailable", "unavailable"],
  ];
  await matrix(permitted);
  const publicDetail = await detail(events[0]);
  const originalLine = publicDetail.participants
    .find((p: { pid: number }) => p.pid === 100)
    .log.split(/\r?\n/)[0];
  // Quote identity is event plus PID; pkill_info.id intentionally differs.
  const quote = await service.createBattleComment(
    events[0],
    "privacy-fixture",
    "freeform body",
    undefined,
    undefined,
    "FORGED",
    1,
    100,
  );
  expect(quote.quotedText).toBe(originalLine);
  await pool.query(
    "INSERT INTO pvp_battle_comments(event_id,account_name,content,parent_id,quoted_text,line_number,participant_id) VALUES(?,?,?,?,?,?,?)",
    [events[0], "privacy-fixture", "freeform reply", quote.id, "STORED_QUOTE", 1, 100],
  );
  for (const [event, pid, line] of [
    [events[0], 101, 1],
    [events[4], 100, 1],
    [events[0], 100, 999],
  ]) {
    await expect(
      service.createBattleComment(
        event,
        "privacy-fixture",
        "body",
        undefined,
        undefined,
        "FORGED",
        line,
        pid,
      ),
    ).rejects.toMatchObject({ statusCode: 400 });
  }
  await pool.query("UPDATE player_data SET act2=0 WHERE pid IN (100,101)");
  await matrix([
    ["private", "private"],
    ["private", "private"],
    ["private", "private"],
    ["private", "private"],
    ["unavailable", "unavailable"],
  ]);
  const hidden = await service.getBattleComments(events[0]);
  expect(JSON.stringify(hidden)).not.toMatch(/STORED_QUOTE|PUBLIC_A_LINE/);
  expect(JSON.stringify(hidden)).toContain("freeform body");
  expect(JSON.stringify(hidden)).toContain("freeform reply");
  settings.respectWebinfoToggle = false;
  await matrix(permitted);
  settings.respectWebinfoToggle = true;
  await pool.query("UPDATE player_data SET act2=134217728 WHERE pid IN (100,101)");
  await matrix(permitted);
  await pool.query("UPDATE player_data SET act2=0 WHERE pid=100");
  await matrix([
    ["private", "private"],
    ["private", "public"],
    ["private", "private"],
    ["private", "public"],
    ["unavailable", "unavailable"],
  ]);
  // Temporarily detach the identity rather than deleting the rest of its synthetic data.
  await pool.query("UPDATE player_data SET pid=102 WHERE pid=100");
  await matrix([
    ["unavailable", "private"],
    ["unavailable", "public"],
    ["private", "private"],
    ["unavailable", "public"],
    ["unavailable", "unavailable"],
  ]);
  settings.respectWebinfoToggle = false;
  await matrix(permitted);
  settings.respectWebinfoToggle = true;
  await pool.query("UPDATE player_data SET pid=100,act2=NULL WHERE pid=102");
  await matrix([
    ["unavailable", "private"],
    ["unavailable", "public"],
    ["private", "private"],
    ["unavailable", "public"],
    ["unavailable", "unavailable"],
  ]);
  await pool.query("UPDATE player_data SET act2=134217728 WHERE pid=100");
  const [after] = await pool.query(
    "SELECT event_id,pid,webinfo_at_capture,equip,log FROM pkill_info WHERE pid IN (100,101) ORDER BY id",
  );
  expect(after).toEqual(originalConsent);
  await pool.query("UPDATE pkill_info SET webinfo_at_capture=2 WHERE event_id=? AND pid=100", [
    events[3],
  ]);
  expect(
    (await detail(events[3])).participants.find((p: { pid: number }) => p.pid === 100).pov_status,
  ).toBe("unavailable");
  settings.respectWebinfoToggle = false;
  await expect(
    service.createBattleComment(
      events[3],
      "privacy-fixture",
      "body",
      undefined,
      undefined,
      "FORGED",
      1,
      100,
    ),
  ).rejects.toMatchObject({ statusCode: 400 });
  await pool.query("UPDATE pkill_info SET webinfo_at_capture=1 WHERE event_id=? AND pid=100", [
    events[3],
  ]);
  // A renamed capture column models a reader deployed before the additive migration.
  await pool.query("ALTER TABLE pkill_info RENAME COLUMN webinfo_at_capture TO withheld_consent");
  expect(
    (await detail(events[0])).participants.every(
      (p: { pov_status: string }) => p.pov_status === "unavailable",
    ),
  ).toBe(true);
  await pool.query("ALTER TABLE pkill_info RENAME COLUMN withheld_consent TO webinfo_at_capture");
  settings.respectWebinfoToggle = true;
  await matrix(permitted);
  settings.pvpDelayMinutes = 1440;
  expect((await request(app).get(`/api/pvp/events/${events[0]}`)).status).toBe(404);
  settings.pvpDelayMinutes = 0;
  if (process.env.PVP_BROWSER_SCRIPT) {
    app.post("/fixture/webinfo/:value", async (req, res) => {
      await pool.query("UPDATE player_data SET act2=? WHERE pid IN (100,101)", [
        req.params.value === "on" ? 134217728 : 0,
      ]);
      res.json({ saved: true });
    });
    app.get("/api/site-config", (_req, res) =>
      res.json({
        siteTitle: "PvP Fixture",
        siteLogoUrl: "",
        supportUrl: "",
        mudHost: "localhost",
        mudPort: "4000",
        mudPortTls: "",
        mudWsUrl: "wss://localhost/ws",
        frontPageHeroEnabled: false,
        frontPageHeroTitle: "",
        frontPageHeroSubtitle: "",
        frontPageHeroImageUrl: "",
        frontPageContent: "",
      }),
    );
    app.use("/api", (req, res) =>
      res.json(
        req.path.includes("batch/accounts")
          ? { Alice: "privacy-fixture", Bob: "privacy-fixture" }
          : req.path.includes("auth")
            ? null
            : [],
      ),
    );
    app.use(express.static(process.env.PVP_WEB_DIST!));
    app.get(/.*/, (_req, res) => res.sendFile(join(process.env.PVP_WEB_DIST!, "index.html")));
    const server = app.listen(Number(process.env.PVP_WEB_PORT || 0), "127.0.0.1");
    await new Promise<void>((resolve) => server.once("listening", resolve));
    try {
      const address = server.address() as { port: number };
      const result = await promisify(execFile)(process.execPath, [process.env.PVP_BROWSER_SCRIPT], {
        env: { ...process.env, PVP_BASE_URL: `http://127.0.0.1:${address.port}` },
        timeout: 120000,
      });
      process.stdout.write(result.stdout);
    } finally {
      await new Promise<void>((resolve) => server.close(() => resolve()));
    }
  }
  writeFileSync(
    join(directory, "api-result.json"),
    JSON.stringify(
      {
        events,
        passed: [
          "real producer/codec/transaction/anonymous API",
          "capture/current-state matrices",
          "quote/reply gating and canonical creation",
          "unknown/invalid/missing schema",
          "release delay",
          "immutable snapshots",
        ],
      },
      null,
      2,
    ),
  );
}, 180000);
