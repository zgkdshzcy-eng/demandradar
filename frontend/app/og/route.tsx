import { ImageResponse } from "next/og";
import { getLocale, t } from "@/lib/i18n";

export const runtime = "edge";

const SIZE = { width: 1200, height: 630 };

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const locale = getLocale();
  const title = (searchParams.get("title") || "DemandRadar").slice(0, 90);
  const subtitle = (
    searchParams.get("subtitle") || t("og.subtitle.home", locale)
  ).slice(0, 110);
  const kind = searchParams.get("kind") || "home";

  const accent =
    kind === "brief"
      ? "#a855f7"
      : kind === "weekly"
        ? "#3b82f6"
        : kind === "painpoint"
          ? "#f59e0b"
          : "#10b981";
  const score = searchParams.get("score");
  const evidenceCount = searchParams.get("evidence");

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "72px",
          background:
            "linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f172a 100%)",
          color: "white",
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 999,
              background: accent,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 32,
              fontWeight: 700,
            }}
          >
            ⚡
          </div>
          <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: -0.5 }}>
            DemandRadar
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div
            style={{
              fontSize: 64,
              fontWeight: 700,
              lineHeight: 1.1,
              letterSpacing: -1,
              maxWidth: 1000,
            }}
          >
            {title}
          </div>
          <div
            style={{
              fontSize: 32,
              color: "#94a3b8",
              maxWidth: 1000,
              lineHeight: 1.35,
            }}
          >
            {subtitle}
          </div>
          {(score || evidenceCount) && (
            <div style={{ display: "flex", gap: 32, marginTop: 8 }}>
              {score && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12,
                    background: accent, display: "flex",
                    alignItems: "center", justifyContent: "center",
                    fontSize: 24, fontWeight: 700, color: "#fff"
                  }}>
                    {score}
                  </div>
                  <div style={{ fontSize: 20, color: "#94a3b8" }}>Demand Score</div>
                </div>
              )}
              {evidenceCount && (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12,
                    background: "rgba(255,255,255,0.1)", display: "flex",
                    alignItems: "center", justifyContent: "center",
                    fontSize: 24, fontWeight: 700, color: "#e2e8f0"
                  }}>
                    {evidenceCount}
                  </div>
                  <div style={{ fontSize: 20, color: "#94a3b8" }}>Signals</div>
                </div>
              )}
            </div>
          )}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: 22,
            color: "#64748b",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius: 999,
                background: accent,
              }}
            />
            {t("og.footer", locale)}
          </div>
          <div>demandradar.app</div>
        </div>
      </div>
    ),
    SIZE,
  );
}
