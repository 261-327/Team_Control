import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/",
    name: "Сипи",
    short_name: "Сипи",
    description: "Задачи, участники и материалы учебных проектов.",
    lang: "ru",
    start_url: "/my-tasks",
    scope: "/",
    display: "standalone",
    background_color: "#f8f8f8",
    theme_color: "#f8f8f8",
    icons: [
      { src: "/icons/sipi-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/sipi-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      {
        src: "/icons/sipi-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
