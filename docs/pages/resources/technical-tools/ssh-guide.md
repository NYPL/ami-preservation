---
title: SSH Optimization Guide
layout: default
nav_order: 3
parent: Technical Tools
grand_parent: Resources
---

# SSH Workflow Optimization Guide

This guide outlines the steps to streamline the process of connecting to virtual machines via SSH. By implementing these changes, you will eliminate the need to memorize IP addresses and type passwords for every connection.

## Prerequisites
* A local machine with a terminal (macOS, Linux, or Windows WSL/PowerShell).
* Access to the remote server (username and current password).

---

## 1. Password-less Authentication (SSH Keys)
Using SSH keys is more secure than passwords and allows for instant login.

### Step 1: Generate a Key Pair
Check if you already have a key pair. Run this in your local terminal:

```bash
ls ~/.ssh/id_rsa.pub
```

If the file does not exist, generate a new one (press **Enter** through all prompts to accept defaults):

```bash
ssh-keygen -t rsa -b 4096
```

### Step 2: Copy Public Key to Server
Use `ssh-copy-id` to transfer your public key to the remote VM. Replace the placeholders with your actual info.

```bash
ssh-copy-id user@your-server-ip
```
*You will be asked for your password one last time.*

> **Verification:** Try logging in with `ssh user@your-server-ip`. You should not be prompted for a password.

---

## 2. Shortening Hostnames (SSH Config)
The SSH config file allows you to map complex server details to a short nickname. This works for SSH, SCP, Rsync, and VS Code Remote.

1.  Open or create your config file:
    ```bash
    nano ~/.ssh/config
    ```

2.  Add the following configuration block:

    ```text
    Host myvm
        HostName 192.168.1.55
        User remote_username
        # IdentityFile ~/.ssh/id_rsa  <-- Optional: Only needed if using a custom key path
    ```

    | Parameter | Description |
    | :--- | :--- |
    | **Host** | The short name you want to type (e.g., `dev`, `db-server`). |
    | **HostName** | The actual IP address or domain name. |
    | **User** | Your username on the remote server. |

3.  Save the file (`Ctrl+O`, `Enter`) and exit (`Ctrl+X`).

> **Usage:** You can now connect using:
> ```bash
> ssh myvm
> ```

---

## 3. Creating Shell Aliases (Optional)
For the fastest possible access, you can alias the ssh command in your shell profile.

1.  Open your shell configuration file (`~/.bashrc` or `~/.zshrc`).
2.  Add the following line to the bottom of the file:
    ```bash
    alias vm="ssh myvm"
    ```
3.  Reload your configuration:
    ```bash
    source ~/.bashrc  # or ~/.zshrc
    ```

> **Usage:** Type `vm` and press Enter to connect instantly.

---

## Appendix: Connection Stability
If your SSH sessions tend to freeze or drop after periods of inactivity, add the following "Heartbeat" configuration to the top of your `~/.ssh/config` file:

```text
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 2
```