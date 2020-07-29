# This file is Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2016-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2018 John Sully <john@csquare.ca>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

from nmigen import *
from nmigen.lib.scheduler import RoundRobin

from gram.common import *
from gram.core.controller import *
import gram.stream as stream

__ALL__ = ["gramCrossbar"]

class _DelayLine(Elaboratable):
    def __init__(self, delay):
        if delay < 1:
            raise ValueError("delay value must be 1+")
        self.delay = delay

        self.i = Signal()
        self.o = Signal()

    def elaborate(self, platform):
        m = Module()

        buffer = Signal(self.delay)
        m.d.sync += [
            buffer.eq(Cat(self.i, buffer))
        ]
        m.d.comb += self.o.eq(buffer[-1])

        return m

class gramCrossbar(Elaboratable):
    """Multiplexes LiteDRAMController (slave) between ports (masters)

    To get a port to LiteDRAM, use the `get_port` method. It handles data width
    conversion and clock domain crossing, returning LiteDRAMNativePort.

    The crossbar routes requests from masters to the BankMachines
    (bankN.cmd_layout) and connects data path directly to the Multiplexer
    (data_layout). It performs address translation based on chosen
    `controller.settings.address_mapping`.
    Internally, all masters are multiplexed between controller banks based on
    the bank address (extracted from the presented address). Each bank has
    a RoundRobin arbiter, that selects from masters that want to access this
    bank and are not already locked.

    Locks (cmd_layout.lock) make sure that, when a master starts a transaction
    with given bank (which may include multiple reads/writes), no other bank
    will be assigned to it during this time.
    Arbiter (of a bank) considers given master as a candidate for selection if:
     - given master's command is valid
     - given master addresses the arbiter's bank
     - given master is not locked
       * i.e. it is not during transaction with another bank
       * i.e. no other bank's arbiter granted permission for this master (with
         bank.lock being active)

    Data ready/valid signals for banks are routed from bankmachines with
    a latency that synchronizes them with the data coming over datapath.

    Parameters
    ----------
    controller : LiteDRAMInterface
        Interface to LiteDRAMController

    Attributes
    ----------
    masters : [LiteDRAMNativePort, ...]
        LiteDRAM memory ports
    """

    def __init__(self, controller):
        self.controller = controller

        self.rca_bits = controller.address_width
        self.nbanks = controller.nbanks
        self.nranks = controller.nranks
        self.cmd_buffer_depth = controller.settings.cmd_buffer_depth
        self.read_latency = controller.settings.phy.read_latency + 1
        self.write_latency = controller.settings.phy.write_latency + 1

        self.bank_bits = log2_int(self.nbanks, False)
        self.rank_bits = log2_int(self.nranks, False)

        self.masters = []
        self._pending_submodules = []

    def get_native_port(self):
        port = gramNativePort(
            mode="both",
            address_width=self.rca_bits + self.bank_bits - self.rank_bits,
            data_width=self.controller.data_width,
            clock_domain="sync",
            id=len(self.masters))
        self.masters.append(port)
        return port

    def elaborate(self, platform):
        m = Module()

        m.submodules += self._pending_submodules

        controller = self.controller
        nmasters = len(self.masters)
        assert nmasters > 0

        # Address mapping --------------------------------------------------------------------------
        cba_shifts = {"ROW_BANK_COL": controller.settings.geom.colbits - controller.address_align}
        cba_shift = cba_shifts[controller.settings.address_mapping]
        m_ba = [master.get_bank_address(self.bank_bits, cba_shift) for master in self.masters]
        m_rca = [master.get_row_column_address(self.bank_bits, self.rca_bits, cba_shift) for master in self.masters]

        master_readys = [0]*nmasters
        master_wdata_readys = [0]*nmasters
        master_rdata_valids = [0]*nmasters

        arbiters_en = Signal(self.nbanks)
        arbiters = [EnableInserter(arbiters_en[n])(RoundRobin(count=nmasters)) for n in range(self.nbanks)]
        m.submodules += arbiters

        for nb, arbiter in enumerate(arbiters):
            bank = getattr(controller, "bank"+str(nb))

            # For each master, determine if another bank locks it ----------------------------------
            master_locked = []
            for nm, master in enumerate(self.masters):
                locked = Signal()
                for other_nb, other_arbiter in enumerate(arbiters):
                    if other_nb != nb:
                        other_bank = getattr(controller, "bank"+str(other_nb))
                        locked = locked | (other_bank.lock & (other_arbiter.grant == nm))
                master_locked.append(locked)

            # Arbitrate ----------------------------------------------------------------------------
            bank_selected = [(ba == nb) & ~locked for ba,
                             locked in zip(m_ba, master_locked)]
            bank_requested = [bs & master.cmd.valid for bs,
                              master in zip(bank_selected, self.masters)]
            m.d.comb += [
                arbiter.requests.eq(Cat(*bank_requested)),
                arbiters_en[nb].eq(~bank.valid & ~bank.lock)
            ]

            # Route requests -----------------------------------------------------------------------
            m.d.comb += [
                bank.addr.eq(Array(m_rca)[arbiter.grant]),
                bank.we.eq(Array(self.masters)[arbiter.grant].cmd.we),
                bank.valid.eq(Array(bank_requested)[arbiter.grant])
            ]
            master_readys = [master_ready | ((arbiter.grant == nm) & bank_selected[nm] & bank.ready)
                             for nm, master_ready in enumerate(master_readys)]
            master_wdata_readys = [master_wdata_ready | ((arbiter.grant == nm) & bank.wdata_ready)
                                   for nm, master_wdata_ready in enumerate(master_wdata_readys)]
            master_rdata_valids = [master_rdata_valid | ((arbiter.grant == nm) & bank.rdata_valid)
                                   for nm, master_rdata_valid in enumerate(master_rdata_valids)]

        # Delay write/read signals based on their latency
        for nm, master_wdata_ready in enumerate(master_wdata_readys):
            delayline = _DelayLine(self.write_latency)
            m.submodules += delayline
            m.d.comb += delayline.i.eq(master_wdata_ready)
            master_wdata_readys[nm] = delayline.o

        for nm, master_rdata_valid in enumerate(master_rdata_valids):
            delayline = _DelayLine(self.read_latency)
            m.submodules += delayline
            m.d.comb += delayline.i.eq(master_rdata_valid)
            master_rdata_valids[nm] = delayline.o

        for master, master_ready in zip(self.masters, master_readys):
            m.d.comb += master.cmd.ready.eq(master_ready)
        for master, master_wdata_ready in zip(self.masters, master_wdata_readys):
            m.d.comb += master.wdata.ready.eq(master_wdata_ready)
        for master, master_rdata_valid in zip(self.masters, master_rdata_valids):
            m.d.comb += master.rdata.valid.eq(master_rdata_valid)

        # Route data writes ------------------------------------------------------------------------
        with m.Switch(Cat(*master_wdata_readys)):
            for nm, master in enumerate(self.masters):
                with m.Case(2**nm):
                    m.d.comb += [
                        controller.wdata.eq(master.wdata.data),
                        controller.wdata_we.eq(master.wdata.we),
                    ]
            with m.Case():
                m.d.comb += [
                    controller.wdata.eq(0),
                    controller.wdata_we.eq(0),
                ]

        # Route data reads -------------------------------------------------------------------------
        for master in self.masters:
            m.d.comb += master.rdata.data.eq(controller.rdata)

        return m
