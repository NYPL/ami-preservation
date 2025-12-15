---
title: Command Line Resources
layout: default
nav_order: 1
parent: Technical Tools
grand_parent: Resources
---
# Resources
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Installing ajv

To use `ajv` (often required for metadata validation), you must install `npm` first.

1.  **Install npm:**
    ```shell
    brew install npm
    ```

2.  **Install ajv-cli:**
    ```shell
    npm install -g ajv-cli
    ```

## Prevent creation of .DS_Store files on network shares

To stop macOS from automatically creating `.DS_Store` files on network drives, run the following commands in Terminal.

**1. Apply the setting:**
```shell
defaults write com.apple.desktopservices DSDontWriteNetworkStores -boolean true
```

**2 Check if it worked:**

```shell
defaults read com.apple.desktopservices DSDontWriteNetworkStores
```

(Should return “true” or “1”)