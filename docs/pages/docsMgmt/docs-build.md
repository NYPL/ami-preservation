---
title: Site Installation and Development
layout: default
parent: Documentation Policy and Content Management
nav_order: 2
---

# Documentation Site Installation and Development
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

## Overview
This documentation site is built with **Jekyll 4** and uses the **Just the Docs** theme. We use **GitHub Actions** for deployment, which means the site is built automatically in the cloud whenever code is pushed to the `main` branch.

To contribute or preview changes locally, you will need to set up a Ruby environment.

## Setting up Ruby Environment with rbenv
We use `rbenv` to manage Ruby versions to avoid conflicts with the system Ruby on macOS. This project currently uses **Ruby 3.2.2**.

### 1. Install rbenv

```bash
brew install rbenv ruby-build
```

### 2. Initialize rbenv in your Shell

Add rbenv to your shell to enable automatic Ruby version switching. Append the following lines to your config file (usually `~/.zshrc` on modern Macs):

```bash
echo 'eval "$(rbenv init -)"' >> ~/.zshrc
```

After editing, restart your terminal or reload your config:

```bash
source ~/.zshrc
```

### 3. Install Ruby 3.2.2

Install the required Ruby version:

```bash
rbenv install 3.2.2
```

Navigate to the project directory. If the repo includes a `.ruby-version` file, rbenv should switch automatically. If not, set it manually:

```bash
rbenv local 3.2.2
```

### 4. Verify Installation

Check that you are running the correct version:

```bash
ruby -v
```

*Output should be `ruby 3.2.2...`*

## Install Project Dependencies

### 1. Clone the Repository

If you haven’t already, clone the repository to your local machine:

```bash
git clone https://github.com/NYPL/ami-preservation.git
```

### 2. Install Dependencies

Navigate to the `docs` folder where the site configuration lives:

```bash
cd ami-preservation/docs
```

Install the required software libraries (Gems):

```bash
gem install bundler
bundle install
```

## Running the Site Locally

You can preview the site on your own computer before pushing changes to GitHub.

1.  Navigate to the docs folder:
    ```bash
    cd /path/to/ami-preservation/docs
    ```
2.  Start the local server:
    ```bash
    bundle exec jekyll serve
    ```
3.  Open your web browser and go to:
    [http://127.0.0.1:4000/ami-preservation/](http://127.0.0.1:4000/ami-preservation/)

*Note: As you edit and save markdown files, the site will auto-regenerate. Refresh your browser to see changes.*

## Deployment (GitHub Actions)
We do not use the legacy "GitHub Pages" gem anymore. Instead, this repository uses a modern **GitHub Actions** workflow.

* **How to Deploy:** Simply commit and push your changes to the `main` branch.
* **What happens next:** GitHub will automatically spin up a server, build the site using the configuration in `.github/workflows/deploy.yml`, and publish it to the live URL.
* **Troubleshooting:** If the live site does not update, check the "Actions" tab in the GitHub repository to see build logs.