import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const PUBLIC_PATHS = ["/login", "/setup-password", "/api/auth/login", "/api/auth/setup-password"];
const COOKIE_NAME = "spartan_session";

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Allow static assets and Next.js internals
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/favicon") ||
    pathname.endsWith(".svg") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".ico")
  ) {
    return NextResponse.next();
  }

  // Check session cookie
  const token = request.cookies.get(COOKIE_NAME)?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Verify JWT
  try {
    const secret = new TextEncoder().encode(
      process.env.JWT_SECRET || "fallback-dev-secret-do-not-use"
    );
    const { payload } = await jwtVerify(token, secret);

    // Check admin-only routes
    if (pathname.startsWith("/admin") || pathname.startsWith("/api/admin")) {
      if (payload.role !== "admin") {
        return NextResponse.redirect(new URL("/", request.url));
      }
    }

    // Attach user info to headers for downstream use
    const response = NextResponse.next();
    response.headers.set("x-user-id", payload.id as string);
    response.headers.set("x-user-email", payload.email as string);
    response.headers.set("x-user-name", payload.name as string);
    response.headers.set("x-user-role", payload.role as string);
    return response;
  } catch {
    // Invalid or expired token — clear cookie and redirect
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete(COOKIE_NAME);
    return response;
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
