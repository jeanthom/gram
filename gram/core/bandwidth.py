# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 John Sully <john@csquare.ca>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

"""LiteDRAM Bandwidth."""

from nmigen import *

from lambdasoc.periph import Peripheral

__ALL__ = ["Bandwidth"]

# Bandwidth ----------------------------------------------------------------------------------------

class Bandwidth(Peripheral, Elaboratable):
    """Measures LiteDRAM bandwidth

    This module works by counting the number of read/write commands issued by
    the controller during a fixed time period. To copy the values registered
    during the last finished period, user must write to the `update` register.

    Parameters
    ----------
    cmd : Endpoint(cmd_request_rw_layout)
        Multiplexer endpoint on which all read/write requests are being sent
    data_width : int, in
        Data width that can be read back from CSR
    period_bits : int, in
        Defines length of bandwidth measurement period = 2^period_bits

    Attributes
    ----------
    update : CSR, in
        Copy the values from last finished period to the status registers
    nreads : CSRStatus, out
        Number of READ commands issued during a period
    nwrites : CSRStatus, out
        Number of WRITE commands issued during a period
    data_width : CSRStatus, out
        Can be read to calculate bandwidth in bits/sec as:
            bandwidth = (nreads+nwrites) * data_width / period
    """
    def __init__(self, cmd, data_width, period_bits=24):
        self.update     = CSR()
        self.nreads     = CSRStatus(period_bits + 1)
        self.nwrites    = CSRStatus(period_bits + 1)
        self.data_width = CSRStatus(bits_for(data_width), reset=data_width)
        self._period_bits = period_bits

    def elaborate(self, platform):
        m = Module()

        cmd_valid    = Signal()
        cmd_ready    = Signal()
        cmd_is_read  = Signal()
        cmd_is_write = Signal()
        self.sync += [
            cmd_valid.eq(cmd.valid),
            cmd_ready.eq(cmd.ready),
            cmd_is_read.eq(cmd.is_read),
            cmd_is_write.eq(cmd.is_write)
        ]

        counter   = Signal(self._period_bits)
        period    = Signal()
        nreads    = Signal(self._period_bits + 1)
        nwrites   = Signal(self._period_bits + 1)
        nreads_r  = Signal(self._period_bits + 1)
        nwrites_r = Signal(self._period_bits + 1)
        m.d.sync += Cat(counter, period).eq(counter + 1)

        with m.If(period):
            m.d.sync += [
                nreads_r.eq(nreads),
                nwrites_r.eq(nwrites),
                nreads.eq(0),
                nwrites.eq(0),
            ]

            with m.If(cmd_valid & cmd_ready):
                with m.If(cmd_is_read):
                    m.d.sync += nreads.eq(1)

                with m.If(cmd_is_write):
                    m.d.sync += nwrites.eq(1)
        with m.Elif(cmd_valid & cmd_ready):
            with m.If(cmd_is_read):
                m.d.sync += nreads.eq(nreads + 1)

            with m.If(cmd_is_write):
                m.d.sync += nwrites.eq(nwrites + 1)

        with m.If(self.update.re):
            m.d.sync += [
                self.nreads.status.eq(nreads_r),
                self.nwrites.status.eq(nwrites_r),
            ]

        return m
