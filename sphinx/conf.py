# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.append('/Users/hanssen.henrik/PycharmProjects/hpy/hpy')

# -- Project information -----------------------------------------------------

project = 'hpy'
# noinspection PyShadowingBuiltins
copyright = '2019, Henrik Hanssen'
author = 'Henrik Hanssen'

# The full version, including alpha/beta/rc tags
release = ''
for _line in open('../hpy/__version__.py', 'r').read().split('\n'):
    if '__version__' in _line and ' = ' in _line:
        release = _line.split(' = ')[1].lstrip('\'').rstrip('\'')

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc', 'sphinx.ext.doctest', 'sphinx_automodapi.automodapi'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# for read the docs
master_doc = 'index'


# -- Options for HTML output -------------------------------------------------

# create with sphinx-build -b html sphinx/rst documentation

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
# html_theme = 'alabaster'
html_theme = 'default'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']


# -- Extension configuration -------------------------------------------------
numpydoc_show_class_members = False
pygments_style = 'sphinx'