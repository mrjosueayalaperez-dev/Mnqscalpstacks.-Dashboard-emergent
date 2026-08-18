export const PAYMENT_LINKS = {
  pro: "https://buy.stripe.com/bJe8wO0rB0un8rQ6oQ8so08",
  premium: "https://buy.stripe.com/5kQdR80rBb91gYmfZq8so01",
  elite: "https://buy.stripe.com/8x214mden6SLfUi5kM8so07",
};

export const paymentLinkFor = (tier, email) => {
  const base = PAYMENT_LINKS[tier];
  if (!base) return null;
  return email ? `${base}?prefilled_email=${encodeURIComponent(email)}` : base;
};
