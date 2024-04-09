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

## Setting up Ruby Environment with rbenv
If you're working on a project that requires Ruby, using rbenv to manage Ruby versions can help avoid compatibility issues. Follow these steps to set up Ruby 3.1.0 for Jekyll projects:

### Install rbenv

```brew install rbenv```

### Initialize rbenv in your Shell

Add rbenv to your shell to enable automatic Ruby version switching. Append the following lines to ~/.zshrc:

```eval "$(rbenv init -)"```

After editing, restart your terminal or source your .zshrc file to apply the changes:

```source ~/.zshrc```

### Install Ruby 3.1.0

As of April 2024, Jekyll requires Ruby version 3.1.0 or higher, but not 3.3. Install Ruby 3.1.0 using rbenv:

```rbenv install 3.1.0```
```rbenv global 3.1.0```

Note: The global command sets the default Ruby version for all terminals. If you only want to set Ruby 3.1.0 for a specific project, use rbenv local 3.1.0 within the project directory.

### Verify Installation

```ruby -v```

You should see Ruby 3.1.0 as the output. If not, revisit the previous steps for potential corrections.

## Install Dependencies

### Install Jekyll and Bundler

```gem install jekyll bundler```

### Set Up Your Project

If you haven’t already, clone the repository to your desired location:

git clone <https://github.com/NYPL/ami-preservation.git> <optional-local-directory>

Navigate to the /docs site folder within your local copy of the repository:

```cd /path/to/your-project/docs```

### Install Project Dependencies

Run the following command to install the necessary Ruby gems specified in your project's Gemfile:

```bundle install```

## Editing Pages and Testing Site Changes Locally

* Edit Markdown files using a text editor
* Save and commit changes to the repo.
* Run ```cd /path/to/ami-preservation/docs/```
* Run ```bundle exec jekyll serve```
* Open your Web Browser and navigate to [http://localhost:4000](http://localhost:4000)
* Reload page as needed to view changes in real time.
