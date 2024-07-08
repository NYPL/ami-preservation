---
title: Configuring Environmental Variables for Scripts
layout: default
nav_order: 2
parent: Resources
---

# Configuring Environmental Variables for Scripts

Certain scripts utilized in our workflows, such as `clean_spec_csv_to_excel.py`, `fmrest_barcode`, and `digitization_performance_tracker.py`, require specific environmental variables to be set in your `.zshrc` file to function correctly. These variables typically include API keys, tokens, configuration settings, and database credentials necessary for the scripts to interact with external services like Trello, FileMaker, and AMI Database.

**Setting up Environmental Variables:**

1. **Open your Terminal application.**
2. **Access your `.zshrc` file by typing:**
   ```bash
   open -e ~/.zshrc
   ```
   This command will open your `.zshrc` file in TextEdit. If the file does not exist, it will be created.

3. **Add the required environmental variables.** Below are examples of how you might configure your `.zshrc` for our specific scripts:

   - For `clean_spec_csv_to_excel.py`, which interfaces with Trello:
     ```bash
     export TRELLO_API_KEY='your_trello_api_key'
     export TRELLO_TOKEN='your_trello_token'
     export TRELLO_LIST_ID='your_trello_list_id'
     ```
   - For `fmrest_barcode`, which requires FileMaker server details:
     ```bash
     export FILEMAKER_SERVER='your_filemaker_server'
     export FILEMAKER_DATABASE='your_filemaker_database'
     export FILEMAKER_LAYOUT='your_filemaker_layout'
     ```
  - For `digitization_performance_tracker.py`, which requires AMI Database connection details:
     ```bash
    export FM_SERVER='<server_ip>'
    export AMI_DATABASE='<database_name>'
    export AMI_DATABASE_USERNAME='<username>'
    export AMI_DATABASE_PASSWORD='<password>'
     ```

4. **Save and close TextEdit.** After adding your variables, save the changes and close the editor.

5. **Apply the changes by typing the following in Terminal:**
   ```bash
   source ~/.zshrc
   ```
   This command reloads your `.zshrc`, applying the new environmental settings.

**Installing and Configuring Java (OpenJDK 11)**

1. **Install OpenJDK 11 using Homebrew**
   ```bash
   brew install openjdk@11
   ```
2. **Add OpenJDK 11 to your environment**
   ```bash
  echo 'export PATH="/usr/local/opt/openjdk@11/bin:$PATH"' >> ~/.zshrc
  echo 'export JAVA_HOME="/usr/local/opt/openjdk@11"' >> ~/.zshrc
   ```

3. **Reload your .zshrc file**
   ```bash
   source ~/.zshrc
   ```
4. **Verify the Java installation**
   ```bash
   java -version
   ```

**Verification:**

- To verify that the environmental variables are set correctly, you can echo them in the Terminal. For example:
  ```bash
  echo $TRELLO_API_KEY
  ```
  This should display the value you set for the TRELLO_API_KEY variable.

**Troubleshooting:**

- If changes to `.zshrc` do not seem to apply, make sure you have saved the file after editing and run `source ~/.zshrc` again.
- If a script fails to recognize the variables, ensure that there are no typos in your `.zshrc` file and that all variable names are correct.

By setting up these variables as instructed, users will ensure smooth operation of scripts requiring specific configurations, supporting effective digitization and preservation workflows.
