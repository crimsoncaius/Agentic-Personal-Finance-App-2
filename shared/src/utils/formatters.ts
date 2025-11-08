// Utility functions for formatting data

export const formatAmount = (
  amount: number | string | undefined,
  direction: string
): string => {
  // Handle undefined, null, or invalid amounts
  if (amount === undefined || amount === null || amount === "") {
    return direction === "expense" ? "-$0.00" : "+$0.00";
  }

  // Convert to number, handling both strings and numbers
  const numAmount =
    typeof amount === "string" ? parseFloat(amount) : Number(amount);

  // Handle NaN case
  if (isNaN(numAmount)) {
    return direction === "expense" ? "-$0.00" : "+$0.00";
  }

  // Always use the absolute value and apply the correct sign based on direction
  const sign = direction === "expense" ? "-" : "+";
  return `${sign}$${Math.abs(numAmount).toFixed(2)}`;
};

export const formatDate = (dateString: string | Date): string => {
  try {
    // Handle both string and Date objects
    const date =
      typeof dateString === "string" ? new Date(dateString) : dateString;

    // Check if date is valid
    if (isNaN(date.getTime())) {
      return "Invalid Date";
    }

    const day = date.getDate().toString().padStart(2, "0");
    const month = (date.getMonth() + 1).toString().padStart(2, "0");
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  } catch (error) {
    console.error("Error formatting date:", error, "Input:", dateString);
    return "Invalid Date";
  }
};
