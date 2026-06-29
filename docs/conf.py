# Configuration file for Sphinx documentation builder.

import os
import sys

# Add packages to path for autodoc
sys.path.insert(0, os.path.abspath('../packages/chat-orchestrator/src'))
sys.path.insert(0, os.path.abspath('../packages/liturgy-agent/src'))
sys.path.insert(0, os.path.abspath('../packages/homily-agent/src'))
sys.path.insert(0, os.path.abspath('../packages/a2a-protocol/src'))

project = 'Prete-a-porter'
copyright = '2026, Development Team'
author = 'Development Team'
version = '0.1.0'
release = '0.1.0'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx.ext.intersphinx',
    'sphinx_autodoc_typehints',
    'myst_parser',
]

# Autodoc options
autodoc_typehints = 'description'
autodoc_member_order = 'bysource'

# Napoleon settings (for Google/NumPy style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_method = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = False
napoleon_use_param = True
napoleon_use_keyword = True
napoleon_use_rtype = True

# MyST parser settings
myst_enable_extensions = [
    "dollarmath",
    "linkify",
    "tasklist",
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# HTML theme
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']

html_theme_options = {
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'vcs_pageview_mode': '',
    'style_nav_header_background': '#2980B9',
}

# Intersphinx mapping
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'fastapi': ('https://fastapi.tiangolo.com/', None),
}
