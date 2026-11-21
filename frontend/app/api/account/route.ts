import { profile } from "../../../lib/profile-data";
import { apiOrigin, apiPrefix } from "../../../lib/api-origin.mjs";
import type { components } from "../../schema";
export async function GET() {
  try {
    const params = new URLSearchParams({
      client_id: profile.clientId,
      limit: "200",
    });
    const result = await fetch(apiOrigin + apiPrefix + "/transfers?" + params, {
      cache: "no-store",
    });
    if (!result.ok) return new Response(null, { status: 502 });
    const feed: components["schemas"]["TransferListResponse"] =
      await result.json();
    return Response.json(
      feed.transfers.map(
        ({ transfer_id, recipient_name, created_at, amount, status }) => ({
          transfer_id,
          recipient_name,
          created_at,
          amount,
          status,
        }),
      ),
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    return new Response(null, { status: 503 });
  }
}
