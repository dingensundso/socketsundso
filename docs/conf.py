# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

import os
import sys
sys.path.insert(0, os.path.abspath('../'))
import socketsundso

# -- Project information -----------------------------------------------------

project = 'socketsundso'
copyright = '2022, Markus Bach'
author = 'Markus Bach'
release = socketsundso.__version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
html_title = f"socketsundso Documentation {release}"
html_show_sourcelink = False
html_use_index = False
html_domain_indices = False

html_theme_options = {
    'description': "A WebSocket JSON API Framework based on FastAPI, pydantic and starlette",
    'show_relbar_bottom': True,
    'extra_nav_links': {
        'PyPI': 'https://pypi.org/project/socketsundso/',
        'GitHub': 'https://github.com/dingensundso/socketsundso/',
    }
}

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
        'donate.html',
    ]
}
