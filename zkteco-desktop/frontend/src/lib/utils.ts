import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { configAPI } from "./api";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Cache for resource domain
let resourceDomainCache: string = "";

// Event name for resource domain updates
export const RESOURCE_DOMAIN_EVENT = "resource-domain:changed";

// Get resource domain from config
export async function getResourceDomain(): Promise<string> {
  if (resourceDomainCache) {
    return resourceDomainCache;
  }

  try {
    const config = await configAPI.getConfig();
    resourceDomainCache = (config.RESOURCE_DOMAIN || "").trim();
    return resourceDomainCache;
  } catch (error) {
    console.error("Failed to get resource domain:", error);
    resourceDomainCache = "";
    return "";
  }
}

// Build full avatar URL from avatar_url field
export function buildAvatarUrl(
  avatarUrl: string | null | undefined,
  resourceDomain?: string,
): string | undefined {
  if (!avatarUrl) {
    return undefined;
  }

  // If avatar_url is already a full URL (starts with http:// or https://), return as is
  if (avatarUrl.startsWith("http://") || avatarUrl.startsWith("https://")) {
    return avatarUrl;
  }

  // If no resource domain provided or empty, return avatar_url as is
  if (!resourceDomain || resourceDomain.trim() === "") {
    return avatarUrl;
  }

  // Remove trailing slash from resource domain
  const domain = resourceDomain.replace(/\/$/, "");

  // Add leading slash to avatar_url if it doesn't have one
  const path = avatarUrl.startsWith("/") ? avatarUrl : `/${avatarUrl}`;

  return `${domain}${path}`;
}

// Clear cache (useful when config is updated). Optional hint lets listeners avoid refetching.
export function clearResourceDomainCache(nextDomain?: string) {
  resourceDomainCache = (nextDomain || "").trim();

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent<{ resourceDomain: string }>(RESOURCE_DOMAIN_EVENT, {
        detail: { resourceDomain: resourceDomainCache },
      }),
    );
  }
}
