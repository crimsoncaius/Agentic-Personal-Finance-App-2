# API Routes Audit for Authentication Integration

## Overview

This document audits the current backend API routes to identify authentication requirements and plan necessary changes for user isolation.

## Current API Architecture

### Authentication Status

- **No Authentication Middleware**: All endpoints are currently public
- **No User Context**: No user identification in requests or responses
- **No Authorization Headers**: No JWT token validation
- **Shared Data Access**: All users can access all data

## Route Analysis

### 1. Entry Routes (`/api/v1/entries`)

#### GET `/api/v1/entries/` - List Entries

- **Current State**: Returns all entries from all users
- **Protection Level**: HIGH - Must be user-scoped
- **Parameters**:
  - `limit`, `offset` (pagination)
  - `date_from`, `date_to`, `direction`, `category_id` (filtering)
  - `amount_min`, `amount_max`, `q` (search), `sort`
- **Required Changes**:
  - Add JWT token validation middleware
  - Extract `user_id` from JWT payload
  - Filter queries by `user_id` in database layer
  - Update `EntryService.get_entries()` to include user_id parameter

#### POST `/api/v1/entries/` - Create Entry

- **Current State**: Creates entries without user association
- **Protection Level**: HIGH - Must be user-scoped
- **Required Changes**:
  - Add JWT token validation middleware
  - Extract `user_id` from JWT payload
  - Include `user_id` in entry creation
  - Update `EntryService.create_entry()` to include user_id parameter

#### PATCH `/api/v1/entries/{entry_id}` - Update Entry

- **Current State**: Can update any entry by ID
- **Protection Level**: HIGH - Must verify ownership
- **Required Changes**:
  - Add JWT token validation middleware
  - Verify entry belongs to authenticated user
  - Update `EntryService.update_entry()` to check ownership

#### DELETE `/api/v1/entries/{entry_id}` - Delete Entry

- **Current State**: Can delete any entry by ID
- **Protection Level**: HIGH - Must verify ownership
- **Required Changes**:
  - Add JWT token validation middleware
  - Verify entry belongs to authenticated user
  - Update `EntryService.delete_entry()` to check ownership

### 2. Chat Routes (`/api/v1/chat`)

#### GET `/api/v1/chat/service-info` - Service Information

- **Current State**: Returns NLP service configuration
- **Protection Level**: LOW - Can remain public (system info)
- **Required Changes**: None (can remain public)

#### POST `/api/v1/chat/` - Chat Query

- **Current State**: Processes queries without user context
- **Protection Level**: HIGH - Must be user-scoped
- **Required Changes**:
  - Add JWT token validation middleware
  - Extract `user_id` from JWT payload
  - Pass `user_id` to NLP service for user-scoped queries
  - Ensure AI responses are filtered to user's data only

### 3. Category Routes (`/api/v1/categories`)

#### GET `/api/v1/categories/` - List Categories

- **Current State**: Returns all system categories
- **Protection Level**: LOW - Categories may remain global
- **Decision Required**:
  - Option A: Keep global (shared categories across all users)
  - Option B: Make user-specific (users can create custom categories)
- **Recommendation**: Keep global for MVP, consider user-specific in future

## Service Layer Analysis

### EntryService

**Current Methods**:

- `create_entry()` - No user_id parameter
- `get_entries()` - No user filtering
- `update_entry()` - No ownership verification
- `delete_entry()` - No ownership verification

**Required Changes**:

```python
# Example updated method signatures
async def create_entry(user_id: UUID, amount: Decimal, ...):
async def get_entries(user_id: UUID, params: EntryQueryParams):
async def update_entry(user_id: UUID, entry_id: UUID, updates: EntryUpdate):
async def delete_entry(user_id: UUID, entry_id: UUID):
```

### CategoryService

**Current State**: No user context needed (if keeping global)
**Future Considerations**: May need user-specific categories later

### NLPService

**Current State**: No user context in queries
**Required Changes**: Add user_id to query processing for data filtering

## Database Query Impact

### Current Queries (No User Filtering)

```sql
-- Current entry queries
SELECT * FROM entry ORDER BY entry_date DESC LIMIT 10;
SELECT * FROM entry WHERE id = $1;
INSERT INTO entry (amount_cents, direction, ...) VALUES (...);
```

### Required Queries (User-Scoped)

```sql
-- Updated entry queries with user filtering
SELECT * FROM entry WHERE user_id = $1 ORDER BY entry_date DESC LIMIT 10;
SELECT * FROM entry WHERE id = $1 AND user_id = $2;
INSERT INTO entry (user_id, amount_cents, direction, ...) VALUES ($1, ...);
```

## Authentication Middleware Requirements

### JWT Token Validation

```python
# Required middleware structure
async def verify_jwt_token(request: Request, call_next):
    # 1. Extract token from Authorization header
    # 2. Verify JWT signature with Supabase public key
    # 3. Extract user_id from JWT payload
    # 4. Add user_id to request state
    # 5. Continue to route handler
```

### Error Handling

- **401 Unauthorized**: Invalid or missing JWT token
- **403 Forbidden**: Valid token but insufficient permissions
- **Token Expiration**: Handle refresh token flow

## Implementation Plan

### Phase 2: Database Schema Changes

1. Add `user_id` column to `entry` table
2. Create foreign key constraint to `auth.users(id)`
3. Add database index for performance
4. Update all entry-related queries

### Phase 3: Backend Authentication

1. Create JWT validation middleware
2. Update all route handlers to extract user_id
3. Modify service layer methods to include user_id
4. Update database queries for user filtering
5. Add proper error handling for auth failures

### Phase 4: Frontend Integration (Future)

1. Add JWT token to API requests
2. Handle authentication errors in frontend
3. Implement login/logout functionality
4. Add session management

## Security Considerations

### Current Vulnerabilities

1. **Data Leakage**: Users can see all entries from all users
2. **Unauthorized Access**: No verification of data ownership
3. **No Session Management**: No secure token handling

### Required Security Measures

1. **Row Level Security (RLS)**: Implement at database level
2. **JWT Validation**: Verify all tokens with Supabase
3. **User Context**: Ensure all operations are user-scoped
4. **Input Validation**: Validate user_id matches token payload

## Testing Requirements

### Authentication Tests

- [ ] Valid JWT token allows access
- [ ] Invalid JWT token returns 401
- [ ] Expired JWT token returns 401
- [ ] Missing JWT token returns 401

### Authorization Tests

- [ ] Users can only access their own entries
- [ ] Users cannot access other users' entries
- [ ] Entry creation includes correct user_id
- [ ] Entry updates verify ownership

### Data Isolation Tests

- [ ] User A cannot see User B's entries
- [ ] User A cannot modify User B's entries
- [ ] User A cannot delete User B's entries
- [ ] Chat responses are filtered to user's data

## Migration Strategy

### Backward Compatibility

- Current API contracts will be maintained
- Frontend changes will be minimal (just adding auth headers)
- Database changes will be additive (new user_id column)

### Rollback Plan

- Database migration can be rolled back if needed
- Backend changes can be feature-flagged
- Frontend can fall back to unauthenticated mode

## Notes

- Categories may remain global for MVP simplicity
- Future phases can add user-specific categories
- Chat service needs significant updates for user context
- Database migration is the critical first step
