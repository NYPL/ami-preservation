---
title: AWS CLI & SSO Configuration
layout: default
nav_order: 5
parent: Technical Tools
grand_parent: Resources
---

# AWS CLI & SSO Configuration

## 1. What is the AWS CLI?
The **AWS Command Line Interface (CLI)** is a unified tool that allows us to control Amazon Web Services directly from the terminal. Instead of clicking through the web-based AWS Console to upload files or manage servers, we can write scripts and commands to automate these tasks in our preservation workflows.

### Background: Why We Switched to IAM Identity Center (SSO)

Historically, accessing AWS required long-term "Access Keys" (an ID and a Secret Key). However, managing these across our **12+ AWS accounts** created significant "tech debt" and security risks. Static keys can be lost, stolen, or accidentally committed to code repositories, and manually rotating them for tens of users became a source of friction.

**We have shifted to IAM Identity Center (Single Sign-On).**
Instead of permanent keys, you now log in using your organizational credentials. This provides:
* **Better Security:** You receive temporary, short-lived credentials that expire automatically.
* **Centralized Access:** You don't need different passwords for our QA, Dev, and Prod accounts.
* **Reduced Friction:** No more manual rotation of access keys.

---

## 2. Installation
We install the AWS CLI using Homebrew.

1.  Open your terminal.
2.  Run the following command:

```bash
brew install awscli
```

3.  Verify the installation by checking the version:
```bash
aws --version
```

---

## 3. Setting Up: Configuring SSO


You only need to do this **once per profile**. The `aws configure sso` command will update your local `~/.aws/config` file with the necessary details to find our organization's login portal.

**Reference:** For specific details like the **SSO start URL**, please refer to the internal IT documentation on Confluence (NYPL AD credentials required):
[How do I set up AWS IAM Identity Center](https://newyorkpubliclibrary.atlassian.net/wiki/spaces/DOPS/pages/651624449/How+do+I+set+up+AWS+IAM+Identity+Center)

Run the interactive setup command:

```bash
aws configure sso
```

You will be prompted for the following details:

| Prompt | What to Enter |
| :--- | :--- |
| **SSO start URL** | Enter our organization's AWS SSO URL (see link above). |
| **SSO Region** | Enter the region where our IAM Identity Center lives (usually `us-east-1`). |
| **Choose AWS account** | The CLI will list accounts you have access to. Select the relevant one (e.g., `preservation-prod`). |
| **Choose a role** | Select your permission set (e.g., `PowerUser` or `Administrator`). |
| **CLI profile name** | **Crucial:** Give this a short, memorable name. You will type this often. (e.g., `preservation-admin` or `my-dev-account`). |

---

## 4. Daily Workflow: Login and Session Management
Because SSO credentials are temporary, you must log in at the start of your session (or whenever your token expires).

### Logging In
To authorize a specific profile:

```bash
aws sso login --profile <your-profile-name>
```

**What happens next?**
1.  The CLI will open your default web browser.
2.  You will see a code on the screen; confirm the authorization in the browser.
3.  Once verified, the browser will say "Request approved," and your terminal will report a successful login.

### Logging Out
To remove locally stored tokens and invalidate the session:

```bash
aws sso logout
```
*Note: This clears your local cache. Server-side roles may persist until their duration timer expires.*

### Checking Your Profiles
If you forget the names of the profiles you created, list them with:

```bash
aws configure list-profiles
```

---

## 5. Running Commands
Once logged in, you must tell the AWS CLI *which* profile to use for every command. You have two ways to do this:

### Option A: The `--profile` Flag (Good for one-off commands)
Append the profile flag to every command you run.

*Example: Listing S3 buckets in the dev account:*
```bash
aws s3 ls --profile my-dev-account
```

### Option B: Environmental Variable (Good for whole sessions)
If you are working in a single account for a while, you can set the profile for your current shell session. You won't need to type the flag again until you close the window.

**Note:** This method is highly recommended when using our internal Python scripts, such as [`copy_to_s3.py`](https://github.com/NYPL/ami-preservation/blob/main/ami_scripts/copy_to_s3.py). By setting the variable, the script will automatically inherit the correct permissions without needing to hardcode credentials.

```bash
export AWS_PROFILE=my-dev-account
# Now you can run commands (or Python scripts) without the flag:
aws s3 ls
python3 copy_to_s3.py
```