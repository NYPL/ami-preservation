# ami-preservation
The Media Preservation teams at the New York Public Library (NYPL) are dedicated to ensuring long-term preservation and access for our audiovisual collections. This repository houses a collection of resources, tools, and internal documentation that underpin our digitization, quality assurance, and quality control efforts within the Audio and Moving Image (AMI) workflow. Explore the repository using the links provided below to access the various tools available:

## [AMI Production Scripts](https://github.com/NYPL/ami-preservation/tree/main/ami_scripts)
## [AMI QC Scripts](https://github.com/NYPL/ami-preservation/tree/main/qc_utilities)
## [AMI Documentation Site](https://nypl.github.io/ami-preservation/)
### Documentation Site Installation and Development
Administrators must set up their site development environment before attempting to make changes to any documents, so they can test funcitonality on the live site before releasing it to the public. Below are the installation instructions.

#### Installation

* See this site for ruby / gem / bundler troubleshooting:
https://idratherbewriting.com/documentation-theme-jekyll/mydoc_install_jekyll_on_mac.html

* If you don’t have ruby: ```brew install ruby```
* If ruby is not in usr/local/bin: ```echo 'export PATH="/usr/local/opt/ruby/bin:$PATH"' >> ~/.bash_profile```

  * Quit & restart Terminal 
  * Open Terminal and check again: ```which ruby``` and ```which gem``` (again, [see here](https://idratherbewriting.com/documentation-theme-jekyll/mydoc_install_jekyll_on_mac.html) for info on installing ruby in the correct location)
  * All set!? (if not, seek help with a human)

* Install dependencies
  1. Run ```gem install Jekyll```
  2. Run ```gem install bundler```
  3. Clone the ami-repository repository to desired location (or update local existing copy)
  4. Navigate to /docs site folder: ```cd /path/to/ami-preservation/docs```
  6. Run ```bundle```

#### Editing Pages and Testing Site Changes Locally
* Edit Markdown files using a text editor (such as Atom or Sublime Text)
* Save and commit changes to the repo.
* Run ```cd /path/to/ami-preservation/docs/```
* Run ```bundle exec jekyll serve```
* Open your Web Browser and navigate to [http://localhost:4000](http://localhost:4000)
* Reload page as needed to view changes in real time.
