// API Configuration for Mobile App
import { Platform } from "react-native";

// Determine the correct API URL based on environment and platform
function getApiBaseUrl(): string {
  if (!__DEV__) {
    return (
      process.env.EXPO_PUBLIC_API_BASE_URL_PROD ||
      "https://agentic-personal-finance-app-2-production.up.railway.app/api/v1"
    );
  }

  // In development, use environment variable if set
  if (process.env.EXPO_PUBLIC_API_BASE_URL_DEV) {
    return process.env.EXPO_PUBLIC_API_BASE_URL_DEV;
  }

  // Auto-detect emulator vs physical device
  if (Platform.OS === "android") {
    // Android emulator uses special IP to access host machine
    // Check if we're likely on an emulator (you can enhance this detection)
    return "http://10.0.2.2:8000/api/v1"; // Android emulator
  } else if (Platform.OS === "ios") {
    // iOS simulator can use localhost
    return "http://localhost:8000/api/v1"; // iOS simulator
  }

  // Fallback: assume physical device needs local IP
  // Update this to your actual local IP address for physical device testing
  return "http://192.168.1.49:8000/api/v1"; // Physical device
}

const API_BASE_URL = getApiBaseUrl();

export { API_BASE_URL };
