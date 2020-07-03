# Low level simulation

This folder contains code used for low level simulation of various aspects of gram.

## Requirements

 * Icarus Verilog (built from latest sources)
 * ECP5 instances models from a Lattice Diamond installation (just install Lattice Diamond)

## Available simulations

### simcrg

Simulates the CRG used in ECPIX5 gram tests and checks for a few assertions.

```
./runsimcrg.sh
```

Produces `simcrg.fst` (compatbile with Gtkwave).

### simsoc

Simulates a full SoC with a UART Wishbone master and a DDR3 model, and sends the init commands that libgram would send over serial.

```
./runsimsoc.sh
```

Produces `simsoc.fst` (compatible with Gtkwave).
