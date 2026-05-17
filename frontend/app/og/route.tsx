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
        : "#10b981";

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
