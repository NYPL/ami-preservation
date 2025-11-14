# ami-preservation

The **Audio and Moving Image (AMI) Preservation** team at the **New York Public Library (NYPL)** is dedicated to ensuring the long-term preservation and access of the Library's audiovisual collections. This repository houses a collection of resources, tools, and internal documentation that underpin our digitization, quality assurance, and quality control efforts.  

Explore the repository using the following links:

- 📜 [**AMI Production Scripts**](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts)  
- 🧭 [**AMI Documentation Site**](https://nypl.github.io/ami-preservation/)

---

## 🚀 Installation

This project includes two types of dependencies that must be installed:

1. **System-level tools** (e.g., `ffmpeg`, `sox`, etc.)
2. **Python packages** (e.g., `pandas`, `boto3`, etc.)

Follow these steps to set up your environment:

---

### 1. Install System Dependencies

First, install the external command-line tools that the Python scripts rely on.

#### macOS (using [Homebrew](https://brew.sh/))

If you don’t have Homebrew, install it first. Then run the following command in your terminal:

```bash
brew install ffmpeg sox mediaconch mkvtoolnix mediainfo
```

> **Note:** Add any other required tools such as `rawcooked` or `makemkv` if your scripts depend on them.

#### Linux / Windows

Use your system’s package manager (e.g., `apt-get` for Ubuntu or `winget` for Windows) to install equivalent packages.

---

### 2. Install Python Package & Scripts

Once the system tools are installed, use `pip` to install the NYPL AMI Preservation package. This will:

- Download the project from GitHub  
- Install all required Python packages (e.g., `pandas`, `boto3`, etc.)  
- Make all 60+ scripts available as runnable commands in your terminal  

```bash
python3 -m pip install -v git+https://github.com/NYPL/ami-preservation
```

---

### 3. Update Your Shell

Your shell must be made aware of the new commands.

If you are using **pyenv** (recommended):

```bash
pyenv rehash
```

If not, simply open a new terminal session to refresh your shell environment.

---

### 4. Test It!

You’re all set! You can now run any script as a direct command.  
Try running one with the `--help` flag to verify it’s working:

```bash
validate-ami-bags --help
```
