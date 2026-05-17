import { NextResponse, type NextRequest } from "next/server";

const COOKIE_NAME = "dr_lang";
const SUPPORTED = new Set(["en", "zh"]);

export function middleware(request: NextRequest) {
  const lang = request.nextUrl.searchParams.get("lang")?.toLowerCase();
  if (!lang || !SUPPORTED.has(lang)) {
    return NextResponse.next();
  }

  const url = request.nextUrl.clone();
  url.searchParams.delete("lang");

  const response = NextResponse.redirect(url, 308);
  response.cookies.set({
    name: COOKIE_NAME,
    value: lang,
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  return response;
}

export const config = {
  matcher: [
    "/",
    "/pricing",
    "/sample",
    "/radar",
    "/briefs",
    "/briefs/:path*",
    "/insights",
    "/insights/:path*",
  ],
};
