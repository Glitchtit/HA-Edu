# Onboarding Indicator Feature

## Overview
This feature adds an onboarding status indicator to the instance list for administrators, allowing them to quickly see which student instances have completed the onboarding process.

## What Changed

### Backend Changes (app.py)
- Modified the `get_instances()` API endpoint to check onboarding status for each instance when accessed by an admin
- Uses the existing `check_instance_onboarding_complete()` function to determine if an instance has been onboarded
- Adds an `onboarded` boolean field to each instance in the response

### Frontend Changes (templates/index.html)
- Added a new "Onboarded" field in the instance information display
- Shows "Ja" (Yes) with a green badge if the instance has been onboarded
- Shows "Nej" (No) with a blue/purple badge if the instance has not been onboarded
- This field is only visible to administrators (wrapped in `{% if is_admin %}`)

## How It Works

1. When an admin views the instance list, the `/api/instances` endpoint is called
2. For each instance, the backend checks if the onboarding is complete by examining the instance's Docker volume for required authentication files
3. The onboarding status is added to the instance data as a boolean field
4. The frontend displays this status with a color-coded badge

## Onboarding Detection Logic

An instance is considered "onboarded" when both of the following files exist in the instance's volume:
- `.storage/auth` - Contains user authentication data
- `.storage/auth_provider.homeassistant` - Contains Home Assistant authentication provider configuration

These files are created when a student completes the initial Home Assistant onboarding wizard.

## Display Format

For administrators, each instance card now shows:
```
Port: 8123
Status: running
Skapad: 2025-11-02
Skapad av: student@example.com
Onboarded: Ja ✓  (or)  Nej
```

## Use Cases

This feature helps administrators:
- Identify which students have started using their instances
- See which instances are ready for teacher access (which requires onboarding to be complete)
- Monitor student progress in getting started with Home Assistant
- Quickly identify instances that may need attention or guidance

## Testing

A comprehensive test suite was created in `test_onboarding_indicator.py` that verifies:
- The onboarding check function exists
- The get_instances endpoint adds onboarding status
- The template displays the onboarding indicator
- The display is restricted to admin users only
