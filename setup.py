#!/usr/bin/env python3

from setuptools import setup
from setuptools import find_packages


setup(
    name="gram",
    description="DRAM core for LambdaSoC",
    author="LambdaConcept",
    author_email="contact@lambdaconcept.com",
    url="https://lambdaconcept.com",
    download_url="https://github.com/lambdaconcept/gram",
    license="BSD",
    python_requires="~=3.6",
    install_requires=[],
    packages=find_packages(exclude=("test*", "doc*", "examples*", "contrib*", "libgram*")),
    include_package_data=True,
)
