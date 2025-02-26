---
title: tmux guide
layout: default
nav_order: 8
parent: Resources
---

# 📌 tmux: Installation & Usage Guide

`tmux` (Terminal Multiplexer) is a powerful tool that allows you to manage multiple terminal sessions within a single SSH connection. It ensures long-running tasks continue even if your SSH session disconnects.

---

## 📥 Installation

### Linux (Debian/Ubuntu)
```bash
sudo apt update && sudo apt install tmux
```

### Linux (CentOS/RHEL)
```bash
sudo yum install tmux
```

### macOS (via Homebrew)
```bash
brew install tmux
```

### Windows (via WSL)
Ensure you have WSL installed, then:
```bash
sudo apt update && sudo apt install tmux
```

Verify installation with:
```bash
tmux -V
```

---

## 🚀 Basic Usage

### 1. Start a New tmux Session
```bash
tmux new -s my_session
```
- `my_session` is an optional session name for easier management.

### 2. Detach from the Session (Keep Running in Background)
Press:
```
Ctrl + B, then D
```
- This allows the session to continue running even if you close your SSH connection.

### 3. Reattach to an Existing Session
```bash
tmux attach -t my_session
```
- If you didn’t name the session, check running sessions:
  ```bash
  tmux ls
  ```

### 4. List All Active Sessions
```bash
tmux ls
```

### 5. Kill a tmux Session
```bash
tmux kill-session -t my_session
```
- To kill **all** tmux sessions:
  ```bash
  tmux kill-server
  ```

---

## 🎨 Multi-Window & Pane Management

### 1. Create a New Window
Inside tmux, press:
```
Ctrl + B, then C
```
- Creates a new terminal window inside your tmux session.

### 2. Switch Between Windows
- Next window:  
  ```
  Ctrl + B, then N
  ```
- Previous window:  
  ```
  Ctrl + B, then P
  ```
- List all windows:  
  ```
  Ctrl + B, then W
  ```

### 3. Split Panes Horizontally
```
Ctrl + B, then "
```

### 4. Split Panes Vertically
```
Ctrl + B, then %
```

### 5. Switch Between Panes
```
Ctrl + B, then Arrow Key
```

### 6. Close a Pane
```
Ctrl + B, then X
```
(Confirm with `Y`)

---

## 🛠 Troubleshooting

### 1. "Error Connecting to /tmp/tmux-1000/default"
Try:
```bash
rm -rf /tmp/tmux-*
tmux new -s my_session
```
Or check `/tmp` permissions:
```bash
ls -ld /tmp
sudo chmod 1777 /tmp
```

### 2. tmux Not Found
Ensure installation:
```bash
which tmux
```
If not installed, follow the installation steps above.

---

## 🏆 Advanced Tips

### Customize tmux with `.tmux.conf`
Add the following to `~/.tmux.conf` for a better experience:
```bash
# Enable mouse support
set -g mouse on

# Start numbering windows from 1 instead of 0
set -g base-index 1

# Set a more intuitive split pane behavior
bind | split-window -h
bind - split-window -v
unbind '"'
unbind %
```
Apply changes:
```bash
tmux source ~/.tmux.conf
```

---

## 📚 Further Reading

- [tmux Cheat Sheet](https://tmuxcheatsheet.com/)
- [tmux GitHub Repo](https://github.com/tmux/tmux)
- [tmux Man Page](https://man7.org/linux/man-pages/man1/tmux.1.html)
