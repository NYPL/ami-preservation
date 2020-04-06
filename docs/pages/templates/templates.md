---
title: Templates
layout: default
nav_order: 14
has_children: true
permalink: /docs/templates/index
---


# Templates
The templates included provide starter pages for short, single-page documents (childless pages) and longer, multi-page documents (pages with children and grand children). For example, this page is the parent of [Parent Document](parent-document-template) and [Childless Document](childless-document-template) and the grand parent of [Child Document](child-document-template).

## Notes
Below are some notes on formatting, YAML / Jekyll front matter, and other important things to consider when creating a new page.

### nav_order
* Nav_order depends on whether the page is a parent, child, or grand child, and must be updated in order to display properly. For example, this page has a navigation order that corresponds to the main pages on this site, and this page does not have a parent. Because this page has children, the nav_order for those children begins at ```1```, and the nav_order for any grand children would also begin again at ```1```.