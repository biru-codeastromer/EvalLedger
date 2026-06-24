import type { MetadataRoute } from "next";

const SITE_URL = "https://evalledger.dev";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      // Keep private / authenticated surfaces out of the index.
      disallow: ["/account", "/review", "/auth/", "/login"]
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL
  };
}
