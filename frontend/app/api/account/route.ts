import type { components } from "../../schema";
export async function GET() {
  const origin = process.env.QAQPAN_API_ORIGIN || "http://127.0.0.1:8000";
  try {
    const result = await fetch(
      origin + "/api/v1/analyst/feed?source=TRANSFER&limit=200",
      { cache: "no-store" },
    );
    if (!result.ok) return new Response(null, { status: 502 });
    const feed: components["schemas"]["AnalystFeedResponse"] =
      await result.json();
    return Response.json(
      feed.cards
        .filter((row) => row.client_id === "demo-client")
        .map(({ transfer_id, recipient_name, created_at, amount, status }) => ({
          transfer_id,
          recipient_name,
          created_at,
          amount,
          status,
        })),
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return new Response(null, { status: 503 });
  }
}
