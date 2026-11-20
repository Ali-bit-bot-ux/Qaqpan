"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
export default function Page() {
  const router = useRouter();
  useEffect(() => {
    const legacyRole = window.location.hash.slice(1);
    router.replace(
      ["trusted", "analyst"].includes(legacyRole)
        ? "/" + legacyRole
        : "/client",
    );
  }, [router]);
  return null;
}
