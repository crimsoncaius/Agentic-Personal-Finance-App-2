# Authentication Integration Plan

## Overview
This plan outlines the steps required to introduce email/password authentication to the frontend using Supabase Auth, aligning with the app's existing Supabase usage.

## Goals
- Provide secure user registration and login flows without requiring email confirmation.
- Integrate Supabase Auth with the current frontend architecture.
- Ensure authenticated access to protected data while maintaining a smooth user experience.

## Phase 1: Preparation & Data Modeling
1. **Audit Current Frontend**
   - Identify components/pages requiring protected access (e.g., dashboards, transaction views).
     - `App.tsx` – acts as the main dashboard shell and should only render after verifying an authenticated session.
     - `components/EntriesTable.tsx` – surfaces historical and real-time transaction data that must be scoped to the signed-in user.
     - `components/ChatInterface.tsx` – drives the AI assistant that can read/write entries; ensure prompts and actions are limited to the active `user_id`.
     - Any future analytic or budgeting widgets that consume `/api/v1` data should inherit the same guard pattern from the start.
   - Document current state management and API interaction patterns.
2. **Supabase Project Review**
   - Confirm the Supabase project has Auth enabled and configure sign-up behavior to skip email confirmations.
   - Set up environment variables for Supabase URL and anon/public API key in frontend `.env` files.
3. **Security Baselines**
   - Decide on password requirements (minimum length, complexity) and session expiration policies within Supabase settings.
4. **User Data Model Definition**
   - Introduce a brand-new UUID `user_id` from Supabase Auth that will serve as the foreign key for every user-owned resource.
   - Catalogue all tables/collections (transactions, budgets, goals, etc.) that must become user-specific and note any global/shared data that should remain untouched.
   - Draft updated ERDs or schema diagrams reflecting the new `user_id` relationships.

## Phase 2: Database Schema & Migration Planning
1. **Schema Updates**
   - For both dev and live databases, plan migrations to add a non-nullable `user_id` column (or equivalent relation) to every user-owned table, defaulting to a placeholder only during backfill.
   - Add supporting indexes and foreign-key constraints referencing Supabase Auth's `auth.users` table (or a mirrored `profiles` table if used).
2. **Data Backfill Strategy**
   - Define mapping rules for assigning new Supabase user IDs to existing domain records, creating seed accounts for any legacy data that should remain accessible.
   - Prepare scripts or SQL migrations that safely backfill `user_id` values in dev first, then apply to live once validated.
   - Update custom database utilities under `backend/scripts/db` so they stamp and query by `user_id`, and ensure they run successfully against both dev and live snapshots before promotion.
3. **Environment Promotion**
   - Establish a promotion sequence: dev migration → QA verification → live migration with maintenance window if needed.
   - Document rollback steps in case the migration introduces issues.

## Phase 3: Implementation
1. **Supabase Client Setup**
   - Create or update a singleton Supabase client module in the frontend that reads from environment variables.
2. **Authentication UI**
   - Implement registration and login forms with validation for username/email uniqueness and password strength.
   - Provide feedback for errors returned by Supabase (e.g., existing email, weak password).
3. **Session Management**
   - Use Supabase Auth helpers to listen for auth state changes and persist sessions (e.g., via local storage).
   - Update global state/store to include the authenticated user object and loading/error states.
4. **Protected Routes**
   - Implement route guards or higher-order components to restrict access to authenticated-only pages.
   - Redirect unauthenticated users to the login page and optionally return them to the original destination post-login.
5. **User-Scoped Data Access**
   - Update all data-fetching hooks/services to filter by the authenticated user's `user_id`, ensuring queries are parameterized and resilient to missing sessions.
   - Ensure create/update operations automatically stamp the current `user_id` before persisting records.
   - Refactor supporting database scripts under `backend/scripts/db` (seeders, migrations, maintenance jobs) to require the authenticated `user_id` and to fail fast when it is absent.
6. **Logout & Password Reset**
   - Add logout functionality via `supabase.auth.signOut()`.
   - Enable password reset flow using Supabase's magic link emails and create a reset confirmation page in the frontend.

## Phase 4: Integration with Backend/API
1. **API Security**
   - If the frontend communicates with a backend, ensure API requests include the Supabase session access token (e.g., in `Authorization` headers).
   - Update backend endpoints to validate Supabase JWTs using the Supabase client or middleware.
2. **Role-Based Access (Optional)**
   - If needed later, configure Supabase Row Level Security (RLS) policies to enforce per-user data access.

## Phase 5: Testing & QA
1. **Pre-Migration Testing**
   - Validate migration scripts against snapshots of both dev and live databases to ensure `user_id` assignments are correct and constraints hold.
   - Confirm that legacy data remains queryable via the new user scoping rules.
2. **Unit and Integration Tests**
   - Write tests for auth-related components and utilities, mocking Supabase responses.
3. **End-to-End Testing**
   - Use E2E tests (e.g., Cypress/Playwright) to verify registration, login, logout, and password reset flows.
4. **Manual QA**
   - Verify registration, login, logout, and password reset flows in different environments (dev/staging).
   - Confirm that user-specific data is isolated per account and that new users start with empty datasets unless seeded intentionally.
   - Dry-run the updated `backend/scripts/db` routines (seeders, migrations, maintenance jobs) in staging to ensure they respect the authenticated user's `user_id` and handle missing/legacy data gracefully.

## Phase 6: Deployment & Monitoring
1. **Environment Promotion**
   - Ensure environment variables are configured across dev/staging/prod deployments.
2. **Monitoring**
   - Track authentication events and errors using Supabase dashboard and app analytics.
3. **User Communication**
   - Prepare onboarding materials or in-app messaging to guide users through new authentication features.

## Future Enhancements
- Add multi-factor authentication (MFA) if security requirements increase.
- Introduce social logins via Supabase OAuth providers if user convenience becomes a priority.
- Implement account management features (profile updates, email change) leveraging Supabase Auth APIs.
