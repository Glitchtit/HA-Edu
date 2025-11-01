# Feature: Add Admin Accounts Button

## Summary
Added a new "Add Admin Accounts" button in the manage instances panel that creates teacher admin accounts for all instances at once. Both the new bulk button and the existing individual "Add Teacher Access" button now support resetting/remaking existing accounts.

## Changes Made

### Backend Changes (app.py)

1. **Modified `create_teacher_account()` function**
   - Added new parameter `reset_if_exists` (default: False)
   - When `reset_if_exists=True`, updates the password if the teacher account already exists
   - Returns appropriate messages: "Teacher account created successfully", "Teacher account password reset successfully", or "Teacher account already exists"

2. **Updated `/api/instances/<server_name>/add-teacher-access` endpoint**
   - Now detects if teacher access was already added
   - Automatically sets `reset_if_exists=True` if teacher account exists
   - Allows re-clicking the button to reset the password (useful when students change the admin password)

3. **Added new endpoint `/api/instances/add-teacher-access-all`**
   - Bulk operation that adds teacher access to all instances
   - Requires admin password authentication
   - Skips instances that haven't completed onboarding
   - Automatically resets passwords for instances that already have teacher access
   - Returns detailed results for each instance (success/failed/skipped)
   - Automatically restarts each instance after adding/resetting the account

### Frontend Changes (templates/index.html)

1. **Added "Add Admin Accounts" button**
   - Located in the manage instances panel controls row
   - Hidden by default, shown after admin unlock
   - Only visible when teacher access feature is enabled (TEACHER_USERNAME and TEACHER_PASSWORD configured)
   - Uses the same styling as individual teacher access buttons

2. **Added bulk operation modal**
   - Shows teacher username that will be created
   - Displays informative message about what the operation does
   - Shows detailed results for each instance after completion
   - Auto-reloads page after 3 seconds

3. **Updated individual "Add Teacher Access" buttons**
   - Removed the disabled state when teacher access already exists
   - Buttons now work for both creating and resetting teacher accounts

### Testing

1. **Created new test file: test_teacher_account_reset.py**
   - Tests password reset functionality when `reset_if_exists=True`
   - Tests that existing behavior is preserved when `reset_if_exists=False`
   - Verifies password is actually updated and different from old password
   - Confirms no duplicate accounts are created

2. **All existing tests pass**
   - test_teacher_account_creation.py: ✓ (2 tests)
   - test_teacher_access.py: ✓ (6 tests)
   - test_teacher_access_integration.py: ✓ (4 tests)
   - test_admin_features.py: ✓ (5 tests)
   - test_app.py: ✓ (6 tests)

## Usage

### For Teachers/Administrators:

1. **Initial Setup:**
   - Set `ADMIN_PASSWORD`, `TEACHER_USERNAME`, and `TEACHER_PASSWORD` environment variables
   - Access the portal and click the 🔑 unlock button
   - Enter the admin password

2. **Bulk Operation (New Feature):**
   - After unlocking, click "👨‍🏫 Add Admin Accounts" button
   - Enter admin password
   - View results showing which instances succeeded, failed, or were skipped
   - Each instance is automatically restarted

3. **Individual Operation:**
   - Click the "👨‍🏫 Teacher" button on any instance card
   - If the account doesn't exist, it will be created
   - If the account already exists, the password will be reset
   - Instance is automatically restarted

## Benefits

1. **Time Saving**: Add teacher access to all instances with one click instead of individually
2. **Password Recovery**: Reset teacher passwords if students have changed them (since they are also admins)
3. **Consistent State**: All instances get the same teacher credentials
4. **Error Handling**: Detailed feedback showing which instances succeeded and which failed
5. **Safety**: Skips instances that haven't completed student onboarding

## API Documentation

### POST /api/instances/add-teacher-access-all

Adds teacher admin accounts to all instances.

**Request:**
```json
{
  "admin_password": "your-admin-password"
}
```

**Response:**
```json
{
  "message": "Teacher access operation completed. 3 succeeded, 0 failed, 1 skipped.",
  "teacher_username": "admin",
  "success_count": 3,
  "failed_count": 0,
  "skipped_count": 1,
  "results": [
    {
      "server_name": "Student-Lab-01",
      "status": "success",
      "message": "Teacher account created successfully",
      "restarted": true
    },
    {
      "server_name": "Student-Lab-02",
      "status": "skipped",
      "message": "Onboarding not complete"
    }
  ]
}
```

**Status Codes:**
- 200: Success (check individual results for per-instance status)
- 401: Invalid admin password
- 403: Admin password or teacher access not configured
- 404: No instances found
