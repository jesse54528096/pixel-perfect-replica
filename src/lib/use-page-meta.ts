import { useEffect } from "react";

type PageMeta = {
  title: string;
  description?: string;
  ogTitle?: string;
  ogDescription?: string;
};

function setMeta(attr: "name" | "property", key: string, content: string) {
  let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

// Client-side replacement for TanStack Router's per-route `head()`.
export function usePageMeta({ title, description, ogTitle, ogDescription }: PageMeta) {
  useEffect(() => {
    document.title = title;
    if (description) setMeta("name", "description", description);
    if (ogTitle) setMeta("property", "og:title", ogTitle);
    if (ogDescription) setMeta("property", "og:description", ogDescription);
  }, [title, description, ogTitle, ogDescription]);
}
