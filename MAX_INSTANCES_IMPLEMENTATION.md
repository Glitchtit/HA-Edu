# MAX_INSTANCES Feature Implementation Summary

## Overview
This implementation adds a configurable `MAX_INSTANCES` environment variable to limit how many Home Assistant instances non-admin users can create. The feature includes both client-side UI updates and server-side validation to prevent bypassing the limit.

## Configuration

### Environment Variable
```bash
MAX_INSTANCES=2  # Limit non-admins to 2 instances each
MAX_INSTANCES=1  # Limit non-admins to 1 instance each
MAX_INSTANCES=0  # Unlimited (default if not set)
MAX_INSTANCES=   # Empty also means unlimited
```

### Key Behaviors
- **Default**: Unlimited instances (MAX_INSTANCES=0)
- **Admin users**: Always unlimited, regardless of MAX_INSTANCES setting
- **Non-admin users**: Limited by MAX_INSTANCES value
- **Per-user limit**: Each user (identified by email or IP) has their own separate limit

## Security Features

### Server-Side Validation
1. **Double-check pattern**: Validation occurs twice
   - Once before the lock (fast path)
   - Once inside the lock (prevents race conditions)
   
2. **Request validation**:
   ```python
   # Before creating instance
   can_create, user_count, max_allowed = can_create_instance(request, instances)
   if not can_create:
       return jsonify({'error': f'You have reached the maximum limit...'}), 403
   ```

3. **Race condition prevention**: Re-validation inside the port allocation lock ensures concurrent requests don't bypass the limit

### Client-Side Updates
- Create button disabled when user reaches limit
- Tooltip shows clear message about the limit
- Instance count display shows "Gräns: X/Y" for non-admins

## User Experience

### For Non-Admin Users
- Clear feedback when limit is reached
- Can see their current count vs. limit
- Cannot bypass via HTML editing (server-side validation)
- Each user has separate quota

### For Admin Users
- No limits apply
- Can create unlimited instances
- Admin status determined by:
  - Local network IP (192.168.50.0/24, 10.0.0.0/8, 127.0.0.0/8)
  - Cloudflare Zero Trust authenticated email in ADMINS list

## Technical Implementation

### Backend Changes (app.py)

1. **Configuration Loading**:
   ```python
   MAX_INSTANCES_STR = os.getenv('MAX_INSTANCES', '').strip()
   MAX_INSTANCES = int(MAX_INSTANCES_STR) if MAX_INSTANCES_STR else 0
   ```

2. **Helper Function**:
   ```python
   def can_create_instance(request, instances):
       """Check if user can create a new instance"""
       # Admins always allowed
       if is_admin_user(request):
           return True, 0, 0
       
       # Unlimited if MAX_INSTANCES is 0
       if MAX_INSTANCES == 0:
           return True, 0, 0
       
       # Count user's instances and check limit
       user_id = get_user_identifier(request)
       user_instance_count = sum(1 for inst in instances.values() 
                                 if inst.get('created_by', '') == user_id)
       
       can_create = user_instance_count < MAX_INSTANCES
       return can_create, user_instance_count, MAX_INSTANCES
   ```

3. **Validation in Endpoint**:
   ```python
   @app.route('/api/instances', methods=['POST'])
   def create_instance():
       # Pre-check before lock
       can_create, user_count, max_allowed = can_create_instance(request, load_instances())
       if not can_create:
           return jsonify({'error': '...'}), 403
       
       with _port_allocation_lock:
           # Re-check inside lock
           instances = load_instances()
           can_create, user_count, max_allowed = can_create_instance(request, instances)
           if not can_create:
               return jsonify({'error': '...'}), 403
           # ... create instance
   ```

### Frontend Changes (templates/index.html)

1. **Create Button**:
   ```html
   <button id="addNewBtn" class="add-button" onclick="openModal()" 
           {% if user_has_instance %}disabled title="{{ create_button_tooltip }}"{% endif %}>
       + Skapa ny instans
   </button>
   ```

2. **Instance Counter**:
   ```html
   <div class="instance-count">
       <span id="instanceCount">{{ instances|length }}</span> aktiva instanser
       {% if not is_admin and max_instances > 0 %}
       <span>(Gräns: {{ user_instance_count }}/{{ max_instances }})</span>
       {% endif %}
   </div>
   ```

## Testing

### Unit Tests (test_max_instances.py)
- ✓ Environment variable loading (0, empty, 1, 5)
- ✓ can_create_instance function logic
- ✓ User with 0/1/2 instances scenarios
- ✓ Different users have separate limits
- ✓ Admin bypass functionality
- ✓ Unlimited mode (MAX_INSTANCES=0)
- ✓ Server-side validation presence

### Integration Tests (test_max_instances_integration.py)
- ✓ Homepage loads correctly
- ✓ Non-admin can create first instance
- ✓ Third instance blocked at limit of 2
- ✓ Different users not affected by others' limits
- ✓ Admin users can create unlimited instances
- ✓ Unlimited mode works end-to-end

### Security Scan
- ✓ CodeQL analysis: 0 alerts found
- ✓ No security vulnerabilities detected

## Migration Guide

### From Previous Version
No migration needed. The feature is backward compatible:
- If MAX_INSTANCES is not set, behavior is unlimited (same as before)
- Existing instances are not affected
- No database changes required

### Recommended Settings

**Educational Environment** (multiple students):
```bash
MAX_INSTANCES=1  # Each student gets one instance
```

**Development Environment** (small team):
```bash
MAX_INSTANCES=3  # Each developer can have multiple test instances
```

**Production/Demo** (no limits for authenticated users):
```bash
MAX_INSTANCES=0  # Unlimited
# Or simply don't set the variable
```

## Files Changed
- `.env.example` - Added MAX_INSTANCES documentation
- `app.py` - Added configuration, validation logic, and helper function
- `templates/index.html` - Updated UI to show limits and disable button
- `test_max_instances.py` - New unit tests
- `test_max_instances_integration.py` - New integration tests
- `test_app.py` - Updated to expect MAX_INSTANCES

## Performance Considerations
- Minimal overhead: Validation is O(n) where n is total instances
- Lock contention: No additional lock time (check happens inside existing lock)
- Memory: No additional data structures needed
- Database: No schema changes required

## Future Enhancements (Not in Scope)
- Per-group limits (e.g., different limits for different user groups)
- Time-based limits (e.g., instances expire after X days)
- Resource-based limits (e.g., CPU/memory limits per user)
- Admin UI to view per-user instance counts
