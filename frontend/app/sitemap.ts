import type { MetadataRoute } from "next";

const SITE_URL = "https://evalledger.dev";

// Public, indexable pages. Dynamic benchmark pages are intentionally omitted to
// avoid a build-time API dependency; add a fetch here once a stable public
// listing endpoint is wired for sitemap generation.
const PUBLIC_ROUTES = [
  "",
  "/registry",
  "/contamination",
  "/standard",
  "/docs",
  "/privacy",
  "/terms",
  "/acceptable-use"
];

export default function sitemap(): MetadataRoute.Sitemap {
  return PUBLIC_ROUTES.map((route) => ({
    url: `${SITE_URL}${route}`,
    changeFrequency: "weekly",
    priority: route === "" ? 1 : 0.7
  }));
}
