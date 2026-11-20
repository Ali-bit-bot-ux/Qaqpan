const trustedName = ["Айгерим", "Айгерім"] as const;

export const profile = {
  clientId: "demo-client",
  name: ["Сауле", "Сәуле"],
  cardholder: "SAULE K.",
  lastFour: "4821",
  trustedName,
  contacts: [
    { account: "TEST-FAMILY-01", name: trustedName },
    { account: "TEST-FAMILY-02", name: ["Арман", "Арман"] },
  ],
} as const;
