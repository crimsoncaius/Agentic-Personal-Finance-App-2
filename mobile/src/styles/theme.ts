// Mobile App Theme Configuration

export const colors = {
  // Dark theme matching web app
  background: {
    primary: "#111827", // gray-900
    secondary: "#1f2937", // gray-800
    tertiary: "#374151", // gray-700
    card: "rgba(31, 41, 55, 0.5)", // gray-800/50
  },
  text: {
    primary: "#ffffff",
    secondary: "#d1d5db", // gray-300
    tertiary: "#9ca3af", // gray-400
    muted: "#6b7280", // gray-500
  },
  accent: {
    blue: "#3b82f6", // blue-500
    blueDark: "#2563eb", // blue-600
    purple: "#8b5cf6", // purple-500
    pink: "#ec4899", // pink-500
    green: "#10b981", // emerald-500
    red: "#ef4444", // red-500
  },
  border: {
    primary: "rgba(107, 114, 128, 0.3)", // gray-500/30
    secondary: "rgba(107, 114, 128, 0.5)", // gray-500/50
  },
  gradient: {
    primary: ["#3b82f6", "#8b5cf6"], // blue to purple
    secondary: ["#8b5cf6", "#ec4899"], // purple to pink
  },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const borderRadius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  full: 9999,
};

export const typography = {
  xs: { fontSize: 12, lineHeight: 16 },
  sm: { fontSize: 14, lineHeight: 20 },
  base: { fontSize: 16, lineHeight: 24 },
  lg: { fontSize: 18, lineHeight: 28 },
  xl: { fontSize: 20, lineHeight: 28 },
  "2xl": { fontSize: 24, lineHeight: 32 },
  "3xl": { fontSize: 30, lineHeight: 36 },
};
