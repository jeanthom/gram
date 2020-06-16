# This file is Copyright (c) 2019 David Shah <dave@ds0.me>
# This file is Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# License: BSD

# 1:2 frequency-ratio DDR3 PHY for Lattice's ECP5
# DDR3: 800 MT/s

import math

from nmigen import *
from nmigen.lib.cdc import FFSynchronizer
from nmigen.utils import log2_int

from lambdasoc.periph import Peripheral

import gram.stream as stream
from gram.common import *
from gram.phy.dfi import Interface
from gram.compat import Timeline

# Lattice ECP5 DDR PHY Initialization --------------------------------------------------------------


class ECP5DDRPHYInit(Elaboratable):
    def __init__(self, eclk_cd):
        self.pause = Signal()
        self.stop = Signal()
        self.delay = Signal()
        self._eclk_cd = eclk_cd

    def elaborate(self, platform):
        m = Module()

        new_lock = Signal()
        update = Signal()
        stop = Signal()
        freeze = Signal()
        pause = Signal()
        reset = Signal()

        # DDRDLLA instance -------------------------------------------------------------------------
        _lock = Signal()
        delay = Signal()
        m.submodules += Instance("DDRDLLA",
                                 i_CLK=ClockSignal("sync2x"),
                                 i_RST=ResetSignal(),
                                 i_UDDCNTLN=~update,
                                 i_FREEZE=freeze,
                                 o_DDRDEL=delay,
                                 o_LOCK=_lock
                                 )
        lock = Signal()
        lock_d = Signal()
        m.submodules += FFSynchronizer(_lock, lock)
        m.d.sync += lock_d.eq(lock)
        m.d.sync += new_lock.eq(lock & ~lock_d)

        # DDRDLLA/DDQBUFM/ECLK initialization sequence ---------------------------------------------
        t = 8  # in cycles
        tl = Timeline([
            (1*t,  [freeze.eq(1)]),  # Freeze DDRDLLA
            (2*t,  [stop.eq(1)]),   # Stop ECLK domain
            (3*t,  [reset.eq(1)]),  # Reset ECLK domain
            (4*t,  [reset.eq(0)]),  # Release ECLK domain reset
            (5*t,  [stop.eq(0)]),   # Release ECLK domain stop
            (6*t,  [freeze.eq(0)]),  # Release DDRDLLA freeze
            (7*t,  [pause.eq(1)]),  # Pause DQSBUFM
            (8*t,  [update.eq(1)]),  # Update DDRDLLA
            (9*t,  [update.eq(0)]),  # Release DDRDMMA update
            (10*t, [pause.eq(0)]),  # Release DQSBUFM pause
        ])
        m.submodules += tl
        # Wait DDRDLLA Lock
        m.d.comb += tl.trigger.eq(new_lock)

        # ------------------------------------------------------------------------------------------
        m.d.comb += [
            self.pause.eq(pause),
            self.stop.eq(stop),
            self.delay.eq(delay),
            ResetSignal(self._eclk_cd).eq(reset)
        ]

        return m

# Lattice ECP5 DDR PHY -----------------------------------------------------------------------------


class ECP5DDRPHY(Peripheral, Elaboratable):
    def __init__(self, pads, sys_clk_freq=100e6):
        super().__init__()

        #self.pads = PHYPadsCombiner(pads)
        self.pads = pads
        self._sys_clk_freq = sys_clk_freq

        databits = len(self.pads.dq.o)
        assert databits % 8 == 0

        # CSR
        bank = self.csr_bank()

        self._dly_sel = bank.csr(databits//8, "rw")

        self._rdly_dq_rst = bank.csr(1, "rw")
        self._rdly_dq_inc = bank.csr(1, "rw")
        self._rdly_dq_bitslip_rst = bank.csr(1, "rw")
        self._rdly_dq_bitslip = bank.csr(1, "rw")

        self._burstdet_clr = bank.csr(1, "rw")
        self._burstdet_seen = bank.csr(databits//8, "r")

        self._zero_ev = self.event(mode="rise")

        self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus = self._bridge.bus
        self.irq = self._bridge.irq

        addressbits = len(self.pads.a.o)
        bankbits = len(self.pads.ba.o)
        nranks = 1 if not hasattr(self.pads, "cs_n") else len(self.pads.cs_n)
        databits = len(self.pads.dq.o)
        self.dfi = Interface(addressbits, bankbits, nranks, 4*databits, 4)

        # PHY settings -----------------------------------------------------------------------------
        tck = 2/(2*2*self._sys_clk_freq)
        nphases = 2
        databits = len(self.pads.dq.o)
        nranks = 1 if not hasattr(self.pads, "cs_n") else len(self.pads.cs_n)
        addressbits = len(self.pads.a.o)
        bankbits = len(self.pads.ba.o)
        cl, cwl = get_cl_cw("DDR3", tck)
        cl_sys_latency = get_sys_latency(nphases, cl)
        cwl_sys_latency = get_sys_latency(nphases, cwl)
        rdcmdphase, rdphase = get_sys_phases(nphases, cl_sys_latency, cl)
        wrcmdphase, wrphase = get_sys_phases(nphases, cwl_sys_latency, cwl)
        self.settings = PhySettings(
            phytype="ECP5DDRPHY",
            memtype="DDR3",
            databits=databits,
            dfi_databits=4*databits,
            nranks=nranks,
            nphases=nphases,
            rdphase=rdphase,
            wrphase=wrphase,
            rdcmdphase=rdcmdphase,
            wrcmdphase=wrcmdphase,
            cl=cl,
            cwl=cwl,
            read_latency=2 + cl_sys_latency + 2 + log2_int(4//nphases) + 4,
            write_latency=cwl_sys_latency
        )

    def elaborate(self, platform):
        m = Module()

        m.submodules += self._bridge

        tck = 2/(2*2*self._sys_clk_freq)
        nphases = 2
        databits = len(self.pads.dq.o)
        nranks = 1 if not hasattr(self.pads, "cs_n") else len(self.pads.cs_n)
        addressbits = len(self.pads.a.o)
        bankbits = len(self.pads.ba.o)

        # Init -------------------------------------------------------------------------------------
        m.submodules.init = DomainRenamer("init")(ECP5DDRPHYInit("sync2x"))

        # Parameters -------------------------------------------------------------------------------
        cl, cwl = get_cl_cw("DDR3", tck)
        cl_sys_latency = get_sys_latency(nphases, cl)
        cwl_sys_latency = get_sys_latency(nphases, cwl)

        # Observation
        self.datavalid = Signal(databits//8)

        # DFI Interface ----------------------------------------------------------------------------
        dfi = self.dfi

        bl8_chunk = Signal()
        rddata_en = Signal(self.settings.read_latency)

        # Clock --------------------------------------------------------------------------------
        for i in range(len(self.pads.clk.o)):
            sd_clk_se = Signal()
            m.submodules += Instance("ODDRX2F",
                                     i_RST=ResetSignal("sync2x"),
                                     i_ECLK=ClockSignal("sync2x"),
                                     i_SCLK=ClockSignal(),
                                     i_D0=0,
                                     i_D1=1,
                                     i_D2=0,
                                     i_D3=1,
                                     o_Q=self.pads.clk.o[i]
                                     )

        # Addresses and Commands ---------------------------------------------------------------
        for i in range(addressbits):
            m.submodules += Instance("ODDRX2F",
                                     i_RST=ResetSignal("sync2x"),
                                     i_ECLK=ClockSignal("sync2x"),
                                     i_SCLK=ClockSignal(),
                                     i_D0=dfi.phases[0].address[i],
                                     i_D1=dfi.phases[0].address[i],
                                     i_D2=dfi.phases[1].address[i],
                                     i_D3=dfi.phases[1].address[i],
                                     o_Q=self.pads.a.o[i]
                                     )
        for i in range(bankbits):
            m.submodules += Instance("ODDRX2F",
                                     i_RST=ResetSignal("sync2x"),
                                     i_ECLK=ClockSignal("sync2x"),
                                     i_SCLK=ClockSignal(),
                                     i_D0=dfi.phases[0].bank[i],
                                     i_D1=dfi.phases[0].bank[i],
                                     i_D2=dfi.phases[1].bank[i],
                                     i_D3=dfi.phases[1].bank[i],
                                     o_Q=self.pads.ba.o[i]
                                     )
        controls = ["ras_n", "cas_n", "we_n", "cke", "odt"]
        if hasattr(self.pads, "reset_n"):
            controls.append("reset_n")
        if hasattr(self.pads, "cs_n"):
            controls.append("cs_n")
        for name in controls:
            for i in range(len(getattr(self.pads, name))):
                m.submodules += Instance("ODDRX2F",
                                         i_RST=ResetSignal("sync2x"),
                                         i_ECLK=ClockSignal("sync2x"),
                                         i_SCLK=ClockSignal(),
                                         i_D0=getattr(dfi.phases[0], name)[i],
                                         i_D1=getattr(dfi.phases[0], name)[i],
                                         i_D2=getattr(dfi.phases[1], name)[i],
                                         i_D3=getattr(dfi.phases[1], name)[i],
                                         o_Q=getattr(self.pads, name)[i]
                                         )

        # DQ ---------------------------------------------------------------------------------------
        dq_oe = Signal()
        dqs_oe = Signal()
        dqs_pattern = DQSPattern()
        m.submodules += dqs_pattern
        for i in range(databits//8):
            # DQSBUFM
            dqs_i = Signal()
            dqsr90 = Signal()
            dqsw270 = Signal()
            dqsw = Signal()
            rdpntr = Signal(3)
            wrpntr = Signal(3)
            rdly = Signal(7)
            with m.If(self._dly_sel.w_data[i]):
                with m.If(self._rdly_dq_rst.re):
                    m.d.sync += rdly.eq(0)
                with m.Elif(self._rdly_dq_inc.re):
                    m.d.sync += rdly.eq(rdly + 1)
            datavalid = Signal()
            burstdet = Signal()
            dqs_read = Signal()
            dqs_bitslip = Signal(2)
            with m.If(self._dly_sel.w_data[i]):
                with m.If(self._rdly_dq_bitslip_rst.re):
                    m.d.sync += dqs_bitslip.eq(0)
                with m.Elif(self._rdly_dq_bitslip.re):
                    m.d.sync += dqs_bitslip.eq(dqs_bitslip + 1)
            dqs_cases = {}
            for j, b in enumerate(range(-2, 2)):
                dqs_cases[j] = dqs_read.eq(
                    rddata_en[cl_sys_latency + b:cl_sys_latency + b + 2] != 0)
            m.d.sync += Case(dqs_bitslip, dqs_cases)
            m.submodules += Instance("DQSBUFM",
                                     p_DQS_LI_DEL_ADJ="MINUS",
                                     p_DQS_LI_DEL_VAL=1,
                                     p_DQS_LO_DEL_ADJ="MINUS",
                                     p_DQS_LO_DEL_VAL=4,
                                     # Clocks / Reset
                                     i_SCLK=ClockSignal("sync"),
                                     i_ECLK=ClockSignal("sync2x"),
                                     i_RST=ResetSignal("sync2x"),
                                     i_DDRDEL=self.init.delay,
                                     i_PAUSE=self.init.pause | self._dly_sel.w_data[i],

                                     # Control
                                     # Assert LOADNs to use DDRDEL control
                                     i_RDLOADN=0,
                                     i_RDMOVE=0,
                                     i_RDDIRECTION=1,
                                     i_WRLOADN=0,
                                     i_WRMOVE=0,
                                     i_WRDIRECTION=1,

                                     # Reads (generate shifted DQS clock for reads)
                                     i_READ0=dqs_read,
                                     i_READ1=dqs_read,
                                     i_READCLKSEL0=rdly[0],
                                     i_READCLKSEL1=rdly[1],
                                     i_READCLKSEL2=rdly[2],
                                     i_DQSI=dqs_i,
                                     o_DQSR90=dqsr90,
                                     o_RDPNTR0=rdpntr[0],
                                     o_RDPNTR1=rdpntr[1],
                                     o_RDPNTR2=rdpntr[2],
                                     o_WRPNTR0=wrpntr[0],
                                     o_WRPNTR1=wrpntr[1],
                                     o_WRPNTR2=wrpntr[2],
                                     o_DATAVALID=self.datavalid[i],
                                     o_BURSTDET=burstdet,

                                     # Writes (generate shifted ECLK clock for writes)
                                     o_DQSW270=dqsw270,
                                     o_DQSW=dqsw
                                     )
            burstdet_d = Signal()
            m.d.sync += burstdet_d.eq(burstdet)
            with m.If(self._burstdet_clr.re):
                m.d.sync += self._burstdet_seen.status[i].eq(0)
            with m.If(burstdet & ~burstdet_d):
                m.d.sync += self._burstdet_seen.status[i].eq(1)

            # DQS and DM ---------------------------------------------------------------------------
            dm_o_data = Signal(8)
            dm_o_data_d = Signal(8)
            dm_o_data_muxed = Signal(4)
            m.d.comb += dm_o_data.eq(Cat(
                dfi.phases[0].wrdata_mask[0*databits//8+i],
                dfi.phases[0].wrdata_mask[1*databits//8+i],
                dfi.phases[0].wrdata_mask[2*databits//8+i],
                dfi.phases[0].wrdata_mask[3*databits//8+i],

                dfi.phases[1].wrdata_mask[0*databits//8+i],
                dfi.phases[1].wrdata_mask[1*databits//8+i],
                dfi.phases[1].wrdata_mask[2*databits//8+i],
                dfi.phases[1].wrdata_mask[3*databits//8+i]),
            )
            m.d.sync += dm_o_data_d.eq(dm_o_data)
            dm_bl8_cases = {}
            dm_bl8_cases[0] = dm_o_data_muxed.eq(dm_o_data[:4])
            dm_bl8_cases[1] = dm_o_data_muxed.eq(dm_o_data_d[4:])
            m.d.sync += Case(bl8_chunk, dm_bl8_cases)  # FIXME: use self.comb?
            m.submodules += Instance("ODDRX2DQA",
                                     i_RST=ResetSignal("sync2x"),
                                     i_ECLK=ClockSignal("sync2x"),
                                     i_SCLK=ClockSignal(),
                                     i_DQSW270=dqsw270,
                                     i_D0=dm_o_data_muxed[0],
                                     i_D1=dm_o_data_muxed[1],
                                     i_D2=dm_o_data_muxed[2],
                                     i_D3=dm_o_data_muxed[3],
                                     o_Q=pads.dm[i]
                                     )

            dqs = Signal()
            dqs_oe_n = Signal()
            m.submodules += [
                Instance("ODDRX2DQSB",
                         i_RST=ResetSignal("sync2x"),
                         i_ECLK=ClockSignal("sync2x"),
                         i_SCLK=ClockSignal(),
                         i_DQSW=dqsw,
                         i_D0=0,  # FIXME: dqs_pattern.o[3],
                         i_D1=1,  # FIXME: dqs_pattern.o[2],
                         i_D2=0,  # FIXME: dqs_pattern.o[1],
                         i_D3=1,  # FIXME: dqs_pattern.o[0],
                         o_Q=dqs
                         ),
                Instance("TSHX2DQSA",
                         i_RST=ResetSignal("sync2x"),
                         i_ECLK=ClockSignal("sync2x"),
                         i_SCLK=ClockSignal(),
                         i_DQSW=dqsw,
                         i_T0=~(dqs_pattern.preamble | dqs_oe |
                                dqs_pattern.postamble),
                         i_T1=~(dqs_pattern.preamble | dqs_oe |
                                dqs_pattern.postamble),
                         o_Q=dqs_oe_n
                         ),
                Tristate(pads.dqs_p[i], dqs, ~dqs_oe_n, dqs_i)
            ]

            for j in range(8*i, 8*(i+1)):
                dq_o = Signal()
                dq_i = Signal()
                dq_oe_n = Signal()
                dq_i_delayed = Signal()
                dq_i_data = Signal(8)
                dq_o_data = Signal(8)
                dq_o_data_d = Signal(8)
                dq_o_data_muxed = Signal(4)
                m.d.comb += dq_o_data.eq(Cat(
                    dfi.phases[0].wrdata[0*databits+j],
                    dfi.phases[0].wrdata[1*databits+j],
                    dfi.phases[0].wrdata[2*databits+j],
                    dfi.phases[0].wrdata[3*databits+j],

                    dfi.phases[1].wrdata[0*databits+j],
                    dfi.phases[1].wrdata[1*databits+j],
                    dfi.phases[1].wrdata[2*databits+j],
                    dfi.phases[1].wrdata[3*databits+j])
                )
                m.d.sync += dq_o_data_d.eq(dq_o_data)
                dq_bl8_cases = {}
                dq_bl8_cases[0] = dq_o_data_muxed.eq(dq_o_data[:4])
                dq_bl8_cases[1] = dq_o_data_muxed.eq(dq_o_data_d[4:])
                # FIXME: use self.comb?
                m.d.sync += Case(bl8_chunk, dq_bl8_cases)
                _dq_i_data = Signal(4)
                m.submodules += [
                    Instance("ODDRX2DQA",
                             i_RST=ResetSignal("sync2x"),
                             i_ECLK=ClockSignal("sync2x"),
                             i_SCLK=ClockSignal(),
                             i_DQSW270=dqsw270,
                             i_D0=dq_o_data_muxed[0],
                             i_D1=dq_o_data_muxed[1],
                             i_D2=dq_o_data_muxed[2],
                             i_D3=dq_o_data_muxed[3],
                             o_Q=dq_o
                             ),
                    Instance("DELAYF",
                             p_DEL_MODE="DQS_ALIGNED_X2",
                             i_LOADN=1,
                             i_MOVE=0,
                             i_DIRECTION=0,
                             i_A=dq_i,
                             o_Z=dq_i_delayed
                             ),
                    Instance("IDDRX2DQA",
                             i_RST=ResetSignal("sync2x"),
                             i_ECLK=ClockSignal("sync2x"),
                             i_SCLK=ClockSignal(),
                             i_DQSR90=dqsr90,
                             i_RDPNTR0=rdpntr[0],
                             i_RDPNTR1=rdpntr[1],
                             i_RDPNTR2=rdpntr[2],
                             i_WRPNTR0=wrpntr[0],
                             i_WRPNTR1=wrpntr[1],
                             i_WRPNTR2=wrpntr[2],
                             i_D=dq_i_delayed,
                             o_Q0=_dq_i_data[0],
                             o_Q1=_dq_i_data[1],
                             o_Q2=_dq_i_data[2],
                             o_Q3=_dq_i_data[3],
                             )
                ]
                m.d.sync += dq_i_data[:4].eq(dq_i_data[4:])
                m.d.sync += dq_i_data[4:].eq(_dq_i_data)
                m.d.comb += [
                    dfi.phases[0].rddata[0*databits+j].eq(dq_i_data[0]),
                    dfi.phases[0].rddata[1*databits+j].eq(dq_i_data[1]),
                    dfi.phases[0].rddata[2*databits+j].eq(dq_i_data[2]),
                    dfi.phases[0].rddata[3*databits+j].eq(dq_i_data[3]),
                    dfi.phases[1].rddata[0*databits+j].eq(dq_i_data[4]),
                    dfi.phases[1].rddata[1*databits+j].eq(dq_i_data[5]),
                    dfi.phases[1].rddata[2*databits+j].eq(dq_i_data[6]),
                    dfi.phases[1].rddata[3*databits+j].eq(dq_i_data[7]),
                ]
                m.submodules += [
                    Instance("TSHX2DQA",
                             i_RST=ResetSignal("sync2x"),
                             i_ECLK=ClockSignal("sync2x"),
                             i_SCLK=ClockSignal(),
                             i_DQSW270=dqsw270,
                             i_T0=~(dqs_pattern.preamble | dq_oe |
                                    dqs_pattern.postamble),
                             i_T1=~(dqs_pattern.preamble | dq_oe |
                                    dqs_pattern.postamble),
                             o_Q=dq_oe_n,
                             ),
                    Tristate(pads.dq[j], dq_o, ~dq_oe_n, dq_i)
                ]

        # Read Control Path ------------------------------------------------------------------------
        # Creates a shift register of read commands coming from the DFI interface. This shift register
        # is used to control DQS read (internal read pulse of the DQSBUF) and to indicate to the
        # DFI interface that the read data is valid.
        #
        # The DQS read must be asserted for 2 sys_clk cycles before the read data is coming back from
        # the DRAM (see 6.2.4 READ Pulse Positioning Optimization of FPGA-TN-02035-1.2)
        #
        # The read data valid is asserted for 1 sys_clk cycle when the data is available on the DFI
        # interface, the latency is the sum of the ODDRX2DQA, CAS, IDDRX2DQA latencies.
        rddata_en_last = Signal.like(rddata_en)
        m.d.comb += rddata_en.eq(
            Cat(dfi.phases[self.settings.rdphase].rddata_en, rddata_en_last))
        m.d.sync += rddata_en_last.eq(rddata_en)
        m.d.sync += [phase.rddata_valid.eq(rddata_en[-1])
                     for phase in dfi.phases]

        # Write Control Path -----------------------------------------------------------------------
        # Creates a shift register of write commands coming from the DFI interface. This shift register
        # is used to control DQ/DQS tristates and to select write data of the DRAM burst from the DFI
        # interface: The PHY is operating in halfrate mode (so provide 4 datas every sys_clk cycles:
        # 2x for DDR, 2x for halfrate) but DDR3 requires a burst of 8 datas (BL8) for best efficiency.
        # Writes are then performed in 2 sys_clk cycles and data needs to be selected for each cycle.
        # FIXME: understand +2
        wrdata_en = Signal(cwl_sys_latency + 5)
        wrdata_en_last = Signal.like(wrdata_en)
        m.d.comb += wrdata_en.eq(
            Cat(dfi.phases[self.settings.wrphase].wrdata_en, wrdata_en_last))
        m.d.sync += wrdata_en_last.eq(wrdata_en)
        m.d.comb += dq_oe.eq(wrdata_en[cwl_sys_latency + 2]
                             | wrdata_en[cwl_sys_latency + 3])
        m.d.comb += bl8_chunk.eq(wrdata_en[cwl_sys_latency + 1])
        m.d.comb += dqs_oe.eq(dq_oe)

        # Write DQS Postamble/Preamble Control Path ------------------------------------------------
        # Generates DQS Preamble 1 cycle before the first write and Postamble 1 cycle after the last
        # write. During writes, DQS tristate is configured as output for at least 4 sys_clk cycles:
        # 1 for Preamble, 2 for the Write and 1 for the Postamble.
        m.d.comb += dqs_pattern.preamble.eq(
            wrdata_en[cwl_sys_latency + 1] & ~wrdata_en[cwl_sys_latency + 2])
        m.d.comb += dqs_pattern.postamble.eq(
            wrdata_en[cwl_sys_latency + 4] & ~wrdata_en[cwl_sys_latency + 3])

        return m
