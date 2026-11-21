export default function Logo({ monochrome = false }: { monochrome?: boolean }) {
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 28 28"
      fill="none"
      aria-hidden="true"
    >
      <path
        d="M14 3.5 23 7v6.1c0 5.3-3.8 9-9 11.4-5.2-2.4-9-6.1-9-11.4V7l9-3.5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M16 12.5a2 2 0 1 0-3 1.73v2.52h2v-2.52a2 2 0 0 0 1-1.73Z"
        fill={monochrome ? "currentColor" : "var(--gold)"}
      />
    </svg>
  );
}
