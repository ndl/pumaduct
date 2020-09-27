from setuptools import setup, find_packages
from distutils.extension import Extension
from Cython.Build import cythonize
from codecs import open
from os import path
import pkgconfig

here = path.abspath(path.dirname(__file__))

def pkg_include_dirs(pkg_name):
  includes = []
  for dir in pkgconfig.cflags(pkg_name).split(" "):
    if dir[:2] == "-I":
      includes.append(dir[2:])
    else:
      includes.append(dir)
  return includes

def pkg_libs(pkg_name):
  libs = []
  for dir in pkgconfig.libs(pkg_name).split(" "):
    if dir[:2] == "-l":
      libs.append(dir[2:])
    else:
      libs.append(dir)
  return libs

extensions = [
    Extension("pumaduct.glib", ["pumaduct/glib.pyx"],
        include_dirs = pkg_include_dirs("glib-2.0"),
        libraries = pkg_libs("glib-2.0")
    ),
    Extension("pumaduct.purple_client", ["pumaduct/purple_client.pyx"],
        include_dirs = pkg_include_dirs("purple"),
        libraries = pkg_libs("purple")
    )]

setup(
    name="pumaduct",
    version="0.1.0",
    description="PuMaDuct integrates libpurple-supported IM protocols into Matrix",
    url="https://endl.ch/projects/pumaduct",
    author="Alexander Tsvyashchenko",
    author_email="matrix@endl.ch",
    license="GPLv3",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Topic :: Communications :: Chat"
    ],
    keywords="bridge gateway libpurple matrix purple",
    packages=find_packages(exclude=["contrib", "docs", "pumaduct/layers/tests"]),
    install_requires=[
        "cachetools>=4.1.1",
        "html2text>=2020.1.16",
        "markdown>=3.2.2",
        "python-magic>=0.4.18",
        "sqlalchemy>=1.3.19"
        ],
    data_files=[("/etc/synapse", ["pumaduct.yaml", "synapse-pumaduct.yaml", "pumaduct.log.config"])],
    entry_points={
        "console_scripts": [
            "pumaduct = pumaduct.main:main"
        ]
    },
    ext_modules = cythonize(extensions)
)
