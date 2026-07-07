export const formatPrice = (price) => {
  if (typeof price !== "number") return "0.00";
  return price.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
};
