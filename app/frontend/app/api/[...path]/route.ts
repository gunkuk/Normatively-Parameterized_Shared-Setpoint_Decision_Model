import { NextRequest } from "next/server";
async function proxy(request: NextRequest) {
  const base = process.env.BACKEND_URL || "http://127.0.0.1:8000";
  const target = new URL(
    request.nextUrl.pathname + request.nextUrl.search,
    base,
  );
  const headers = new Headers();
  for (const name of ["authorization", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "content-disposition"]) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    return new Response(upstream.body, {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { detail: "Backend unavailable. Check service health." },
      { status: 502 },
    );
  }
}
export { proxy as GET, proxy as POST };
