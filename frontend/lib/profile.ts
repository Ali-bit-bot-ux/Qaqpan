"use client";

import type { components } from "../app/schema";
import { useText } from "../app/shared";

import { profile } from "./profile-data";

export function useProfile(
  contact?: components["schemas"]["TrustedContactInfo"] | null,
) {
  const t = useText();
  const defaults = t(...profile.trustedName);
  const serverName = contact?.name.trim();
  const name =
    !serverName ||
    profile.trustedName.some(
      (name) => serverName === name || serverName.startsWith(name + " ("),
    )
      ? defaults
      : serverName;
  return { ...profile, firstName: t(...profile.name), trustedName: name };
}
