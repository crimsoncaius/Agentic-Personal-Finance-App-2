import React, { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
} from "react-native";
import { useAuth } from "../contexts/AuthContext";
import EntriesTable from "../components/EntriesTable";
import ChatInterface from "../components/ChatInterface";
import { colors, spacing, borderRadius, typography } from "../styles/theme";

export default function HomeScreen() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState<"entries" | "chat">("entries");
  const { user, logout } = useAuth();

  const handleEntryCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const handleLogout = () => {
    Alert.alert("Sign Out", "Are you sure you want to sign out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: logout },
    ]);
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerContent}>
          <View style={styles.headerLeft}>
            <View style={styles.logo}>
              <Text style={styles.logoText}>$</Text>
            </View>
            <View>
              <Text style={styles.title}>Personal Finance App</Text>
              <Text style={styles.subtitle}>
                Welcome, {user?.name || user?.email}
              </Text>
            </View>
          </View>
          <TouchableOpacity style={styles.logoutButton} onPress={handleLogout}>
            <Text style={styles.logoutButtonText}>Sign Out</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Tab Navigation */}
      <View style={styles.tabContainer}>
        <TouchableOpacity
          style={[styles.tab, activeTab === "entries" && styles.activeTab]}
          onPress={() => setActiveTab("entries")}
        >
          <Text
            style={[
              styles.tabText,
              activeTab === "entries" && styles.activeTabText,
            ]}
          >
            📊 Entries
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === "chat" && styles.activeTab]}
          onPress={() => setActiveTab("chat")}
        >
          <Text
            style={[
              styles.tabText,
              activeTab === "chat" && styles.activeTabText,
            ]}
          >
            💬 Chat
          </Text>
        </TouchableOpacity>
      </View>

      {/* Content */}
      <View style={styles.content}>
        {activeTab === "entries" ? (
          <EntriesTable refreshTrigger={refreshTrigger} />
        ) : (
          <ChatInterface onEntryCreated={handleEntryCreated} />
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  header: {
    backgroundColor: colors.background.secondary,
    paddingTop: spacing.xl,
    paddingBottom: spacing.lg,
    paddingHorizontal: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.primary,
  },
  headerContent: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  logo: {
    width: 40,
    height: 40,
    backgroundColor: colors.accent.blue,
    borderRadius: borderRadius.lg,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  logoText: {
    color: colors.text.primary,
    fontSize: 20,
    fontWeight: "bold",
  },
  title: {
    fontSize: typography.xl.fontSize,
    fontWeight: "bold",
    color: colors.text.primary,
  },
  subtitle: {
    fontSize: typography.sm.fontSize,
    color: colors.text.tertiary,
    marginTop: 2,
  },
  logoutButton: {
    backgroundColor: colors.background.tertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.border.secondary,
  },
  logoutButtonText: {
    color: colors.text.secondary,
    fontSize: typography.sm.fontSize,
    fontWeight: "500",
  },
  tabContainer: {
    flexDirection: "row",
    backgroundColor: colors.background.secondary,
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  tab: {
    flex: 1,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    borderRadius: borderRadius.md,
    marginHorizontal: spacing.xs,
  },
  activeTab: {
    backgroundColor: colors.accent.blue,
  },
  tabText: {
    fontSize: typography.base.fontSize,
    fontWeight: "500",
    color: colors.text.tertiary,
  },
  activeTabText: {
    color: colors.text.primary,
  },
  content: {
    flex: 1,
    padding: spacing.lg,
  },
});
