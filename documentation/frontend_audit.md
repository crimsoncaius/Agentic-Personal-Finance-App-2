# Frontend Audit for Authentication Integration

## Overview

This document audits the current frontend architecture to identify components and patterns that will need authentication integration in future phases.

## Current Frontend Architecture

### Main Components

#### App.tsx

- **Purpose**: Main dashboard shell and application entry point
- **Current State**: No authentication checks
- **Protection Level**: HIGH - Should only render after verifying authenticated session
- **Required Changes** (Future Phase):
  - Add authentication state management
  - Implement route guards or conditional rendering
  - Show login/register forms when unauthenticated
  - Show main app when authenticated

#### EntriesTable.tsx

- **Purpose**: Displays financial transaction history with pagination
- **Current State**: Fetches all entries without user filtering
- **Protection Level**: HIGH - Must be user-scoped
- **Current API Usage**:
  - `apiService.getEntries(limit, offset)` - No user context
  - Calls `/api/v1/entries/` endpoint
- **Required Changes** (Future Phase):
  - Filter entries by authenticated user_id
  - Update API calls to include user context
  - Handle empty state for new users

#### ChatInterface.tsx

- **Purpose**: AI assistant for financial queries and entry creation
- **Current State**: No user context in prompts or actions
- **Protection Level**: HIGH - Must operate within user scope
- **Current API Usage**:
  - `apiService.sendChatMessage(message)` - No user context
  - Calls `/api/v1/chat/` endpoint
- **Required Changes** (Future Phase):
  - Include user_id in chat context
  - Ensure AI actions are scoped to authenticated user
  - Filter responses to user's data only

### API Service Layer

#### services/api.ts

- **Current Implementation**: No authentication headers or user context
- **Endpoints Used**:
  - `GET /api/v1/entries/` - Lists all entries (no filtering)
  - `POST /api/v1/chat/` - Chat with AI (no user context)
- **Required Changes** (Future Phase):
  - Add Authorization header with JWT token
  - Include user_id in request context where needed
  - Handle authentication errors (401, 403)

### State Management

#### Current Approach

- **No Global State Management**: Using React hooks (useState) only
- **Component-Level State**: Each component manages its own state
- **No User Session State**: No tracking of authentication status
- **No Persistence**: No localStorage/sessionStorage usage

#### Required Changes (Future Phase)

- **Add Authentication State**: Track user session, loading states, errors
- **Global State Management**: Consider Context API or state management library
- **Session Persistence**: Store JWT tokens securely
- **User Context**: Make user information available throughout app

### Data Flow Analysis

#### Current Flow

```
User Input → Component State → API Service → Backend → Database
                ↓
            No Authentication Layer
```

#### Required Flow (Future Phase)

```
User Input → Auth Check → Component State → API Service (with JWT) → Backend (with user_id) → Database (user-scoped)
                ↓
            Authentication Layer
```

## Current API Patterns

### Request Patterns

- **No Authorization Headers**: All requests are unauthenticated
- **No User Context**: Backend receives no user identification
- **Public Endpoints**: All endpoints are currently public

### Error Handling

- **Basic Error Handling**: Shows generic error messages
- **No Auth Error Handling**: No handling of 401/403 responses
- **No Session Management**: No token refresh or logout handling

## Security Considerations

### Current Vulnerabilities

1. **No Access Control**: Any user can access any data
2. **No User Isolation**: All entries are shared across users
3. **No Session Management**: No secure token handling
4. **No Input Validation**: Relying entirely on backend validation

### Required Security Measures (Future Phase)

1. **JWT Token Validation**: Verify tokens on every request
2. **User Data Isolation**: Ensure users only see their own data
3. **Secure Token Storage**: Store tokens securely (httpOnly cookies or secure storage)
4. **Session Expiration**: Handle token refresh and expiration
5. **CSRF Protection**: Implement CSRF tokens if needed

## Database Schema Impact

### Current Schema (No User Isolation)

```sql
-- Current entry table (shared across all users)
CREATE TABLE entry (
  id UUID PRIMARY KEY,
  amount_cents BIGINT NOT NULL,
  direction entry_direction NOT NULL,
  -- ... other fields
  -- NO user_id column
);
```

### Required Schema Changes (Future Phase)

```sql
-- Updated entry table (user-scoped)
ALTER TABLE entry ADD COLUMN user_id UUID NOT NULL REFERENCES auth.users(id);
CREATE INDEX idx_entry_user_id ON entry(user_id);

-- Update all queries to filter by user_id
-- Example: SELECT * FROM entry WHERE user_id = $1;
```

## Component Dependencies

### Authentication Dependencies

- **App.tsx** → Needs auth state, login/logout functionality
- **EntriesTable.tsx** → Needs user_id for data filtering
- **ChatInterface.tsx** → Needs user_id for AI context
- **api.ts** → Needs JWT token management

### No Dependencies (Can Remain Unchanged)

- **UI Components**: Styling and layout components
- **Utility Functions**: Date formatting, amount formatting
- **Type Definitions**: API types and interfaces (may need user context additions)

## Implementation Priority

### Phase 1 (Current) - Preparation ✅

- [x] Audit components and identify protection requirements
- [x] Document current API patterns and state management
- [x] Plan database schema changes

### Phase 2 (Next) - Database Migration

- [ ] Add user_id columns to relevant tables
- [ ] Update database queries to filter by user_id
- [ ] Create migration scripts

### Phase 3 (Future) - Frontend Authentication

- [ ] Implement authentication state management
- [ ] Add JWT token handling to API service
- [ ] Create login/register components
- [ ] Add route protection and conditional rendering
- [ ] Update all API calls to include user context

## Notes

- Frontend authentication implementation is deferred until backend user isolation is complete
- Current focus is on backend preparation and database schema changes
- Frontend will continue to work with backend handling authentication at the API level
