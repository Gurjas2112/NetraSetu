import { defineConfig, devices } from "@playwright/test";
import { createPrivateKey, createPublicKey, createSign, generateKeyPairSync, type KeyObject } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// End-to-end runs against the real gateway, Postgres and Garage (scripts/dev_platform.py).
// Identity is the one stand-in: a throwaway signing key whose JWKS is served on JWKS_PORT,
// so the gateway still verifies real RS256 signatures. The key lives in the gitignored
// tests/e2e/.tmp and is reused so every Playwright process signs with the same key.

const python = process.env.PYTHON ?? "python";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tmp = path.join(root, "tests", "e2e", ".tmp");
const JWKS_PORT = 8090;
const ISSUER = `http://127.0.0.1:${JWKS_PORT}/realms/netrasetu`;
const AUDIENCE = "netrasetu-gateway";
const KID = "e2e-signing-key";
const FACILITY = "00000000-0000-4000-8000-0000000000e2";

function signingKey(): KeyObject {
  const file = path.join(tmp, "signing-key.pem");
  if (!fs.existsSync(file)) {
    fs.mkdirSync(tmp, { recursive: true });
    const { privateKey } = generateKeyPairSync("rsa", { modulusLength: 2048 });
    fs.writeFileSync(file, privateKey.export({ type: "pkcs8", format: "pem" }));
  }
  return createPrivateKey(fs.readFileSync(file));
}

function publishJwks(key: KeyObject): string {
  const dir = path.join(tmp, "jwks");
  const certs = path.join(dir, "realms", "netrasetu", "protocol", "openid-connect", "certs");
  fs.mkdirSync(path.dirname(certs), { recursive: true });
  const jwk = createPublicKey(key).export({ format: "jwk" });
  fs.writeFileSync(certs, JSON.stringify({ keys: [{ ...jwk, kid: KID, use: "sig", alg: "RS256" }] }));
  return dir;
}

function screenerToken(key: KeyObject): string {
  const b64 = (value: object) => Buffer.from(JSON.stringify(value)).toString("base64url");
  const now = Math.floor(Date.now() / 1000);
  const header = b64({ alg: "RS256", typ: "JWT", kid: KID });
  const payload = b64({
    iss: ISSUER,
    aud: AUDIENCE,
    sub: "e2e-screener",
    iat: now,
    exp: now + 3600,
    realm_access: { roles: ["screener"] },
    facility_id: FACILITY,
    amr: ["pwd"],
  });
  const signature = createSign("RSA-SHA256").update(`${header}.${payload}`).sign(key).toString("base64url");
  return `${header}.${payload}.${signature}`;
}

function dotenv(file: string): Record<string, string> {
  if (!fs.existsSync(file)) return {};
  const values: Record<string, string> = {};
  for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
    const match = /^\s*([A-Z0-9_]+)\s*=(.*)$/.exec(line);
    if (match) values[match[1]] = match[2].trim();
  }
  return values;
}

const key = signingKey();
const jwksDir = publishJwks(key);

export default defineConfig({
  testDir: "../tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${python} -m http.server ${JWKS_PORT} --bind 127.0.0.1 --directory "${jwksDir}"`,
      url: `${ISSUER}/protocol/openid-connect/certs`,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: `${python} -m uvicorn service.main:create_app --factory --port 8000`,
      cwd: "..",
      url: "http://localhost:8000/healthz",
      env: {
        ...dotenv(path.join(root, ".env")),
        GATEWAY_ENGINE: "fake",
        OIDC_ISSUER: ISSUER,
        OIDC_AUDIENCE: AUDIENCE,
        CORS_ORIGINS: "http://localhost:5173",
      },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173/field",
      env: { VITE_API_BASE: "http://localhost:8000", VITE_DEV_ACCESS_TOKEN: screenerToken(key) },
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
