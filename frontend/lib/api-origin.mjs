export const apiOrigin = (
  process.env.NEXT_PUBLIC_API_URL?.trim() || "http://localhost:8000"
).replace(/\/+$/, "");

export const apiPrefix = "/api/v1";
