# Onboarding Check Fix Summary

## Problem
The "Onboarded" indicator in the admin dashboard was not working correctly. Even when Home Assistant instances had completed their onboarding process (students had created their first user), the dashboard showed them as "not onboarded" (displaying "Nej" instead of "Ja").

## Root Cause
The application has two routes that provide instance data to the admin dashboard:

1. **`index()` route** (`@app.route('/')`) - Renders the initial HTML page with instance data
2. **`get_instances()` API route** (`@app.route('/api/instances')`) - Provides JSON data for dynamic updates

The onboarding check logic was implemented in `get_instances()` but **missing from `index()`**. This meant:
- On initial page load: instances always showed as "not onboarded" ❌
- After JavaScript polling (if implemented): instances would show correct status ✓

## Solution
Added the same onboarding status check to the `index()` function that was already present in `get_instances()`:

```python
else:
    # For admins, add onboarding status to each instance
    for server_name, instance in instances.items():
        volume_name = instance.get('container_name', f'ha-edu-{server_name.lower().replace(" ", "-")}')
        instance['onboarded'] = check_instance_onboarding_complete_cached(volume_name)
```

This 5-line addition ensures that:
- Both routes use the same logic
- Admins see correct onboarding status on initial page load
- The status is cached for 60 seconds to avoid redundant Docker checks

## Files Changed
- `app.py`: Added onboarding check to `index()` function (lines 1011-1015)

## Testing
Created `test_index_onboarding_fix.py` to verify:
1. The `index()` route includes onboarding checks for admins
2. The logic is consistent between `index()` and `get_instances()`

All existing tests pass:
- ✓ `test_onboarding_indicator.py`
- ✓ `test_admin_features.py`
- ✓ `test_index_onboarding_fix.py` (new)

## Security
No security vulnerabilities introduced (verified with CodeQL).
