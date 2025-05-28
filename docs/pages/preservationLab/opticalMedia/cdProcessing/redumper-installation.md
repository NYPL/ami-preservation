---
title: redumper installation and processing
layout: default
nav_order: 3
parent: CD Processing
grand_parent: Optical Media

---

# Building `redumper` for x86_64 on macOS (Intel)

`redumper` is a low-level byte-perfect CD disc dumper that supports incremental dumps, advanced SCSI/C2 error correction, and intelligent audio CD offset detection. This guide provides **step-by-step instructions** for compiling `redumper` from source on **Intel-based macOS (x86_64)**.

## 🔹 **Prerequisites**

Before building `redumper`, ensure you have the required dependencies installed.

### **1️⃣ Install Required Dependencies**

Run the following command to install the necessary build tools:

```sh
brew install llvm@18 ninja cmake
```

### **2️⃣ Clone the Repository**

Download the `redumper` source code from GitHub:

```sh
git clone https://github.com/superg/redumper.git
cd redumper
```

### **3️⃣ Configure the Build for x86_64**

We need to explicitly tell Clang to compile for **x86_64**:

```sh
CXX=$(brew --prefix llvm@18)/bin/clang++ cmake -B build -G "Ninja"   -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON   -DREDUMPER_CLANG_USE_LIBCPP=ON   -DREDUMPER_CLANG_LINK_OPTIONS="-L$(brew --prefix llvm@18)/lib/c++"   -DCMAKE_BUILD_TYPE=Release   -DREDUMPER_VERSION_BUILD=481
```

### **4️⃣ Compile `redumper`**

Run the build process:

```sh
cmake --build build --config Release --verbose
```

### **5️⃣ Move the Binary to `/usr/local/bin`**

Once compiled, move `redumper` to a location in your `PATH`:

```sh
sudo mv build/redumper /usr/local/bin/
chmod +x /usr/local/bin/redumper
```

### **6️⃣ Verify Architecture**

Ensure the binary is compiled for **x86_64**:

```sh
file /usr/local/bin/redumper
```

✅ **Expected Output:**

```
/usr/local/bin/redumper: Mach-O 64-bit executable x86_64
```

### **7️⃣ Run `redumper`**

Verify that `redumper` is working:

```sh
redumper --help
```

## 🔹 **About `redumper`**

`redumper` is an advanced disc imaging tool designed for high-quality preservation of CD, DVD, and Blu-ray media. It features:

- **Raw byte-perfect dumps**
- **SCSI/C2 error correction**
- **Incremental dumping** for refining bad reads
- **Optimized methods for Plextor and LG/ASUS drives**

### **Supported Operating Systems**

- macOS (Intel & Apple Silicon)
- Linux
- Windows

### **Basic Usage**

Once installed, you can use `redumper` to dump a disc by first identifying your drive:

```sh
diskutil list
```

Find the optical drive (e.g., `/dev/disk2`), then unmount it:

```sh
diskutil unmountDisk /dev/disk2
```

Now dump the disc:

```sh
redumper --drive=disk2 --verbose --speed=4 --retries=100 --image-name="my_disc" --image-path="~/Desktop/"
```

## 🔹 **Contributing & Support**

For additional documentation, support, or to contribute to the project, visit the official repository:

🔗 **GitHub:** [https://github.com/superg/redumper](https://github.com/superg/redumper)
