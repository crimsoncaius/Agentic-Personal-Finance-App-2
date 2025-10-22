# Test Users - Supabase Environments

This document contains credentials and user IDs for test accounts in Development and Production Supabase environments.

## 🔵 Development Environment

### Test User 1

- **Email**: `test@example.com`
- **Password**: `testpassword123`
- **User ID**: `595a675a-5f34-407f-b101-628ea0ef31ee`
- **Entries**: 17 entries (10 expenses, 7 income)
- **Total Income**: ~$42,580
- **Total Expenses**: ~$7,287

### Test User 2

- **Email**: `demo@example.com`
- **Password**: `demopassword123`
- **User ID**: `06094aec-1d4c-4f3e-8361-27294e450775`
- **Entries**: 17 entries (9 expenses, 8 income)
- **Total Income**: ~$38,585
- **Total Expenses**: ~$5,663

### System User

- **Email**: `system@example.com`
- **User ID**: `00000000-0000-0000-0000-000000000001`
- **Note**: Reserved system user

---

## 🟢 Production Environment

### Test User 1

- **Email**: `test@example.com`
- **Password**: `testpassword123`
- **User ID**: `3fd41d14-d9ed-4267-98ab-c9511083258f`
- **Entries**: 17 entries (9 expenses, 8 income)
- **Total Income**: ~$38,040
- **Total Expenses**: ~$670

### Test User 2

- **Email**: `demo@example.com`
- **Password**: `demopassword123`
- **User ID**: `5d94cde8-6640-4bd4-8920-93eca2266ff3`
- **Entries**: 16 entries (4 expenses, 12 income)
- **Total Income**: ~$43,835
- **Total Expenses**: ~$391

### System User

- **Email**: `system@example.com`
- **User ID**: `00000000-0000-0000-0000-000000000001`
- **Note**: Reserved system user

---

## 📊 Data Generation Details

### Date Range

- **Start Date**: 6 months back from today
- **End Date**: Today
- **Current Generation**: April 15, 2025 - October 12, 2025

### Entry Patterns

#### Income Categories

- **Salary (Income)**: Monthly recurring ($3,000-$8,000)
- **Freelance (Income)**: Occasional ($500-$3,000, ~30% chance per month)
- **Other Income (Income)**: Rare ($50-$500, ~20% chance per month)

#### Expense Categories

- **Food & Dining**: Very frequent ($5-$80, 40% daily probability)
- **Transportation**: Frequent ($10-$150, 15% daily probability)
- **Housing**: Occasional ($800-$3,000, 8% daily probability)
- **Shopping**: Regular ($20-$500, 12% daily probability)
- **Entertainment**: Regular ($15-$200, 8% daily probability)
- **Healthcare**: Rare ($30-$500, 5% daily probability)
- **Miscellaneous**: Regular ($10-$300, 12% daily probability)

---

## 🛠️ Management Scripts

### Load Users

```bash
# Development
python backend/scripts/db/load_users.py backend/scripts/db/data/test_users.json

# Production
python backend/scripts/db/load_users.py backend/scripts/db/data/test_users_production.json
```

### Load Entries

```bash
# Development
python backend/scripts/db/load_entries.py backend/scripts/db/data/test_users.json

# Production
python backend/scripts/db/load_entries.py backend/scripts/db/data/test_users_production.json
```

### Wipe Data

```bash
# Development (use with caution)
python backend/scripts/db/wipe_data.py --force

# Production (requires manual confirmation)
python backend/scripts/db/wipe_data.py
```

---

## ⚠️ Important Notes

1. **User IDs are auto-generated** by Supabase Auth and cannot be set manually
2. **Different IDs per environment**: The same email will have different UUIDs in dev vs prod
3. **Passwords are for testing only**: Do not use these credentials in real production scenarios
4. **System user reserved**: The system user ID is reserved and should not be modified
5. **Windows encoding fix**: All scripts include UTF-8 encoding fixes for Windows emoji support

---

## 📁 Configuration Files

- **Development**: `backend/scripts/db/data/test_users.json`
- **Production**: `backend/scripts/db/data/test_users_production.json`

---

## 🔐 Security Reminder

⚠️ **This file contains test credentials and should NOT be committed to version control in a real production environment.**

Consider adding this file to `.gitignore` if working with actual sensitive data.

---

_Last Updated: October 12, 2025_
