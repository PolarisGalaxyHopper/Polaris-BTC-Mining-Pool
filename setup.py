# setup.py — fallback for older pip/setuptools that do not read [project] metadata from pyproject.toml.
from setuptools import setup
setup(name="polaris-pool-client", version="0.1.0", description="Polaris Pool — connect your miners through Tor and watch them from your own terminal",
      long_description=open("README.md", encoding="utf-8").read(), long_description_content_type="text/markdown", license="MIT", python_requires=">=3.8",
      py_modules=["polaris_pool_terminal"], entry_points={"console_scripts": ["polaris-pool=polaris_pool_terminal:main"]})
