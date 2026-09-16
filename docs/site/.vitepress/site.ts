export const PUBLIC_SITE = Object.freeze({
  origin: "https://latentrun.github.io",
  base: "/SurgePilot/",
  repository: "https://github.com/latentrun/SurgePilot",
  releases: "https://github.com/latentrun/SurgePilot/releases",
});

export function publicUrl(route = "/") {
  const normalizedRoute = route === "/" ? "" : route.replace(/^\/+/, "");
  return new URL(`${PUBLIC_SITE.base}${normalizedRoute}`, PUBLIC_SITE.origin).href;
}
