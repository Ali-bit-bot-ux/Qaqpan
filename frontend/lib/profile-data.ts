const trustedName = ["Айгерим", "Айгерім"] as const;

export const profile = {
  clientId: "demo-client",
  name: ["Сауле", "Сәуле"],
  displayName: ["Сауле К.", "Сәуле К."],
  cardholder: "SAULE K.",
  lastFour: "4821",
  trustedName,
  motherPhone: "+77000000000",
  exampleAccount: "KZ000000000000000103",
  contacts: [
    { account: "KZ000000000000000101", name: trustedName },
    { account: "KZ000000000000000102", name: ["Арман", "Арман"] },
  ],
} as const;
