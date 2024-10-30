---
title: JDBC Troubleshooting 
layout: default
nav_order: 6
parent: Resources
---

# Troubleshooting JDBC Connectivity for FileMaker Databases

**Overview**:  
JDBC via `jaydebeapi` is essential for AMI Preservation’s digitization productivity tracking, allowing rapid data extraction for near-real-time tracking and analysis using Pandas and Matplotlib. However, FileMaker’s finicky nature introduces potential points of failure, requiring collaboration with Systems and Operations within Preservation and Collections Processing, and sometimes IT, due to limited server access.

This guide covers step-by-step troubleshooting to help resolve JDBC connectivity issues.

## Preparation
1. **Test Connectivity with `test_jdbc.py`**  
   Use the simplified testing script (`test_jdbc.py`) to verify basic server connectivity without database extraction. This script is available [here](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/test_jdbc.py) and can toggle between production and development servers for testing.

## Step-by-Step Troubleshooting

### Step 1: Verify Database ODBC/JDBC Settings
1. **Access ODBC/JDBC Settings**:  
   In FileMaker, go to `File` → `Sharing` → `Enable ODBC/JDBC`.
2. **Ensure ODBC/JDBC is Enabled**:  
   Confirm that ODBC/JDBC sharing is turned **on**.
3. **User Permissions**:  
   Make sure that the users attempting to connect have the required permissions to access the database.

### Step 2: Check User Group Permissions
1. **Open Security Settings**:  
   In FileMaker, navigate to `File` → `Manage` → `Security`.
2. **Review Group Permissions**:  
   Select `Advanced Settings` and confirm that the required user or group has **"Access via ODBC/JDBC"** privileges.

### Step 3: Confirm FileMaker Server Console Settings
1. **Work with Systems and Operations**:  
   Collaborate with a team member from Systems and Operations within PCP to check server console settings.
2. **Enable JDBC in Admin Console**:  
   In the FileMaker Server Admin Console, confirm that JDBC is fully enabled on the production server.

### Step 4: Test Server Connectivity on Port 2399
1. **Install `telnet` (if not already installed)**:  
   Use `homebrew` to install `telnet` by running:
   ```bash
   brew install telnet
   ```
2. **Run Telnet**:  
   In the terminal, enter:
   ```bash
   telnet <server_name> 2399
   ```
   Replace `<server_name>` with the actual server name. This command checks if you can reach the server on port 2399.

### Step 5: Troubleshoot Based on Specific Error Codes
- If the failure message is `(802): Unable to open file`, try connecting to the **development server** using `test_jdbc.py` with the `--use-dev` flag to rule out server-specific issues.

### Step 6: Enlist IT Support if Issues Persist
1. **Request IT Assistance**:  
   If all settings are correct and connectivity issues persist, it may be necessary to enlist support from IT.
2. **Restart the Server**:  
   The production server has a weekly scheduled restart, but sometimes a forced restart can resolve JDBC issues (if things are not working or when in doubt, ask IT to restart Filemaker Windows OS).

---

**Example Error Message and Solution**  
- **Error**: `(802): Unable to open file`
- **Solution**: Restarting the FileMaker Server resolved this issue in the past.

## Additional Notes
- Access to production settings may be limited, so ensure documentation and communication with IT are thorough when requesting assistance.
- The production server restart often resolves lingering issues, making this a useful final step if all else fails.
