---
title: rclone guide
layout: default
nav_order: 2
parent: Technical Tools
grand_parent: Resources
---

# Using rclone with Google Drive

## Step 1: Confirm `rclone` Setup with Google Drive

To check if `rclone` is properly configured with Google Drive, open a terminal and run the following command:

```bash
rclone listremotes
```

If your Google Drive remote appears in the list (e.g., `gdrive:`), it means the remote is configured.

Next, test the connection by listing the contents of your Google Drive:

```bash
rclone lsf gdrive:
```

Replace `gdrive` with the name of your remote if it is named differently. If you see a list of your Google Drive files and folders, the connection is successful.

---

## Step 2: Create a New Google Drive Folder

To create a new folder in Google Drive using `rclone`, use the `mkdir` command with the remote name and folder path:

```bash
rclone mkdir gdrive:/new-folder-name
```

Replace `gdrive` with your remote name and `new-folder-name` with your desired folder name.

---

## Step 3: Copy a File to the New Google Drive Folder

To copy a file to the folder you just created, use the `copy` command with the local file path and the remote folder path:

```bash
rclone copy /path/to/local/file gdrive:/new-folder-name
```

Replace `/path/to/local/file` with the path to the file you want to copy, `gdrive` with your remote name, and `new-folder-name` with the name of the folder you created.

To verify that the file was copied successfully, list the contents of the folder:

```bash
rclone lsf gdrive:/new-folder-name
```

---

## Example Commands

If your remote is named `gdrive`, and you want to create a folder called `backup` and copy a file named `document.txt`, follow these steps:

### Create the folder:
```bash
rclone mkdir gdrive:/backup
```

### Copy the file:
```bash
rclone copy ~/Documents/document.txt gdrive:/backup
```

### Verify the contents of the `backup` folder:
```bash
rclone lsf gdrive:/backup
```

---

## Displaying Copy Progress

To monitor the progress of file transfers, use the `-P` or `--progress` flag with `rclone`.

### Example with Progress Display
```bash
rclone copy /path/to/local/file gdrive:/new-folder-name -P
```

### What You'll See
The `-P` flag provides:
- A progress bar indicating the percentage of the transfer completed.
- Transfer speed (e.g., MB/s).
- Estimated time remaining for the operation to finish.

### Additional Progress-Related Flags
For more detailed output, you can use:
- `-v` or `--verbose`: Shows verbose output about the transfer.
- `-vv`: Enables debug-level output, which is highly detailed.

#### Example with Verbose Output:
```bash
rclone copy /path/to/local/file gdrive:/new-folder-name -P -v
```

This command displays both the progress bar and additional information about each file being transferred.

---

## Copying Multiple Files

`rclone` does not support copying multiple files by listing them directly. Instead, use one of the following methods:

### Option 1: Copy an Entire Directory
```bash
rclone copy /path/to/local/directory gdrive:/remote-folder -P
```
This will copy all files (and subdirectories, if any) from the local directory to the remote folder.

### Option 2: Use a File List
1. Create a text file (`filelist.txt`) with the paths of the files to be copied, one per line:
   ```
   /path/to/file1
   /path/to/file2
   /path/to/file3
   ```
2. Run the command:
   ```bash
   rclone copy --files-from=filelist.txt / gdrive:/remote-folder -P
   ```

### Option 3: Use a Wildcard to Copy Matching Files
```bash
rclone copy /path/to/local/directory gdrive:/remote-folder --include "*.txt" -P
```
This copies all `.txt` files from the local directory to the remote folder.

---

## Handling Errors: `Permission Denied`

If you encounter a **"permission denied"** error when copying files, follow these troubleshooting steps:

### 1. Check Source Directory Permissions
```bash
ls -ld /source/path/
```
Ensure your user has read and write permissions:
```bash
chmod -R u+rw /source/path/
```

### 2. Check Destination Directory Permissions
```bash
ls -ld /destination/path/
chmod -R u+rw /destination/path/
```

### 3. Run as Administrator (if needed)
```bash
sudo rclone copy /source/path/ gdrive:/remote-folder -P
```

### 4. Prevent File Locking Issues
Try using `--local-no-rename`:
```bash
rclone copy /source/path/ gdrive:/remote-folder -P --local-no-rename
```

### 5. Use a Custom Temporary Directory
```bash
rclone copy /source/path/ gdrive:/remote-folder -P --temp-dir /path/to/temp
```

### 6. Check Disk Space
```bash
df -h
```
Ensure you have enough space on both the source and destination.

### 7. Debugging Further
Enable verbose debugging output:
```bash
rclone copy /source/path/ gdrive:/remote-folder -P -vv
```
This will display detailed logs to help identify the cause of the issue.

---

## Conclusion

This guide covers setting up `rclone` with Google Drive, copying files, monitoring progress, handling multiple files, and troubleshooting errors. If you run into any issues, check the logs using `-vv` and ensure your permissions are correctly configured.

For more details, visit the [rclone documentation](https://rclone.org/).
