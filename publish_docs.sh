#!/bin/bash
# rm -rf _doc
# rm -rf _page
autogen_sphinx_docs.py
mkdir _page
cp -r _doc/_build/html/* _page
touch _page/.nojekyll
#git add _page/.nojekyll
git add _page/*
#git add _page
git commit -m "updated docs"
git subtree push --prefix _page origin gh-pages
