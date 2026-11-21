import { apiOrigin, apiPrefix } from "./lib/api-origin.mjs";

export default {
  devIndicators: false,
  experimental: { agentUpgrade: "security" },
  async rewrites() {
    return [
      { source: "/api/schema", destination: apiOrigin + "/openapi.json" },
      {
        source: apiPrefix + "/:path*",
        destination: apiOrigin + apiPrefix + "/:path*",
      },
    ];
  },
};
