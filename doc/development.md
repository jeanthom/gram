# Development

## Unit tests

The complete suite of unit tests can be launched using the [contrib/test](../contrib/test) script.

## Complete simulation

A complete system with a DDR3 model can be simulated using the scripts in the [simulation folder](../gram/simulation/). Those simulations are quite slow (a couple of hours for emulating a few ms). [More informations in the README...](../gram/simulation/README.md)

## Using CI

Running the tests inside a CI environment is highly recommended as it might highlight issues that do not happen on your development computer (eg. files you forgot to commit, issues with the latests versions of nMigen, etc.).
