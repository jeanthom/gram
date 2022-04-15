#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages


setup(
    # Vitals
    name="gram",
    license="BSD",
    url="https://lambdaconcept.com",
    download_url="https://github.com/lambdaconcept/gram",
    author="LambdaConcept",
    author_email="contact@lambdaconcept.com",
    description="DRAM core for LambdaSoC",
    use_scm_version= {
        "root": '..',
        "relative_to": __file__,
        "version_scheme": "guess-next-dev",
        "local_scheme": lambda version : version.format_choice("+{node}", "+{node}.dirty"),
        "fallback_version": "r0.0"
    },

    # Imports / exports / requirements
    platforms='any',
    packages=find_packages(exclude=("test*", "doc*", "examples*", "contrib*", "libgram*")),
    include_package_data=True,
    python_requires="~=3.7",
    install_requires=['nmigen', 'nmigen_boards'],
    setup_requires=['setuptools', 'setuptools_scm'],
    entry_points={},

    # Metadata
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 1 - Planning',
        'Natural Language :: English',
        'Environment :: Plugins',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering',
        ],
)
