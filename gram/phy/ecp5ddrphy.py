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
    def __init__(self):
        self.pause = Signal()
        self.stop = Signal()
        self.delay = Signal()
        self.reset = Signal()

    def elaborate(self, platform):
        m = Module()

        new_lock = Signal()
        update = Signal()
        freeze = Signal()

        # DDRDLLA instance -------------------------------------------------------------------------
        _lock = Signal()
        delay = Signal()
        m.submodules += Instance("DDRDLLA",
            i_CLK=ClockSignal("sync2x"),
            i_RST=ResetSignal("init"),
            i_UDDCNTLN=~update,
            i_FREEZE=freeze,
            o_DDRDEL=delay,
            o_LOCK=_lock)
        lock = Signal()
        lock_d = Signal()
        m.submodules += FFSynchronizer(_lock, lock, o_domain="init")
        m.d.init += lock_d.eq(lock)
        m.d.sync += new_lock.eq(lock & ~lock_d)

        # DDRDLLA/DDQBUFM/ECLK initialization sequence ---------------------------------------------
        t = 8  # in cycles
        tl = Timeline([
            (1*t,  [freeze.eq(1)]),  # Freeze DDRDLLA
            (2*t,  [self.stop.eq(1)]),   # Stop ECLK domain
            (3*t,  [self.reset.eq(1)]),  # Reset ECLK domain
            (4*t,  [self.reset.eq(0)]),  # Release ECLK domain reset
            (5*t,  [self.stop.eq(0)]),   # Release ECLK domain stop
            (6*t,  [freeze.eq(0)]),  # Release DDRDLLA freeze
            (7*t,  [self.pause.eq(1)]),  # Pause DQSBUFM
            (8*t,  [update.eq(1)]),  # Update DDRDLLA
            (9*t,  [update.eq(0)]),  # Release DDRDMMA update
            (10*t, [self.pause.eq(0)]),  # Release DQSBUFM pause
        ])
        m.submodules += tl
        # Wait DDRDLLA Lock
        m.d.comb += tl.trigger.eq(new_lock)

        m.d.comb += self.delay.eq(delay)

        return m

# Lattice ECP5 DDR PHY -----------------------------------------------------------------------------


class ECP5DDRPHY(Peripheral, Elaboratable):
    def __init__(self, pads, sys_clk_freq=100e6):
        super().__init__(name="phy")

        self.pads = pads
        self._sys_clk_freq = sys_clk_freq

        databits = len(self.pads.dq.io)
        if databits % 8 != 0:
            raise ValueError("DQ pads should come in a multiple of 8")

        # CSR
        bank = self.csr_bank()

        self.burstdet = bank.csr(databits//8, "rw")

        self.rdly = []
        self.rdly += [bank.csr(3, "rw", name="rdly_p0")]
        self.rdly += [bank.csr(3, "rw", name="rdly_p1")]

        self._bridge = self.bridge(data_width=32, granularity=8, alignment=2)
        self.bus = self._bridge.bus

        addressbits = len(self.pads.a.o0)
        bankbits = len(self.pads.ba.o0)
        nranks = 1 if not hasattr(self.pads, "cs") else len(self.pads.cs.o0)
        databits = len(self.pads.dq.io)
        self.dfi = Interface(addressbits, bankbits, nranks, 4*databits, 4)

        # PHY settings -----------------------------------------------------------------------------
        tck = 1/(2*self._sys_clk_freq)
        nphases = 2
        databits = len(self.pads.dq.io)
        nranks = 1 if not hasattr(self.pads, "cs") else len(self.pads.cs.o0)
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

        m.submodules.bridge = self._bridge

        tck = 1/(2*self._sys_clk_freq)
        nphases = 2
        databits = len(self.pads.dq.io)

        burstdet_reg = Signal(databits//8, reset_less=True)
        m.d.comb += self.burstdet.r_data.eq(burstdet_reg)

        # Burstdet clear
        with m.If(self.burstdet.w_stb):
            m.d.sync += burstdet_reg.eq(0)

        # Init -------------------------------------------------------------------------------------
        m.submodules.init = init = ECP5DDRPHYInit()

        # Parameters -------------------------------------------------------------------------------
        cl, cwl = get_cl_cw("DDR3", tck)
        cl_sys_latency = get_sys_latency(nphases, cl)
        cwl_sys_latency = get_sys_latency(nphases, cwl)

        # DFI Interface ----------------------------------------------------------------------------
        dfi = self.dfi

        bl8_chunk = Signal()

        # Clock --------------------------------------------------------------------------------
        m.d.comb += [
            self.pads.clk.o_clk.eq(ClockSignal("dramsync")),
            self.pads.clk.o_fclk.eq(ClockSignal("sync2x")),
        ]
        for i in range(len(self.pads.clk.o0)):
            m.d.comb += [
                self.pads.clk.o0[i].eq(0),
                self.pads.clk.o1[i].eq(1),
                self.pads.clk.o2[i].eq(0),
                self.pads.clk.o3[i].eq(1),
            ]

        # Addresses and Commands ---------------------------------------------------------------
        m.d.comb += [
            self.pads.a.o_clk.eq(ClockSignal("dramsync")),
            self.pads.a.o_fclk.eq(ClockSignal("sync2x")),
            self.pads.ba.o_clk.eq(ClockSignal("dramsync")),
            self.pads.ba.o_fclk.eq(ClockSignal("sync2x")),
        ]
        for i in range(len(self.pads.a.o0)):
            m.d.comb += [
                self.pads.a.o0[i].eq(dfi.phases[0].address[i]),
                self.pads.a.o1[i].eq(dfi.phases[0].address[i]),
                self.pads.a.o2[i].eq(dfi.phases[1].address[i]),
                self.pads.a.o3[i].eq(dfi.phases[1].address[i]),
            ]
        for i in range(len(self.pads.ba.o0)):
            m.d.comb += [
                self.pads.ba.o0[i].eq(dfi.phases[0].bank[i]),
                self.pads.ba.o1[i].eq(dfi.phases[0].bank[i]),
                self.pads.ba.o2[i].eq(dfi.phases[1].bank[i]),
                self.pads.ba.o3[i].eq(dfi.phases[1].bank[i]),
            ]

        # Control pins
        controls = ["ras", "cas", "we", "clk_en", "odt"]
        if hasattr(self.pads, "reset"):
            controls.append("reset")
        if hasattr(self.pads, "cs"):
            controls.append("cs")
        for name in controls:
            m.d.comb += [
                getattr(self.pads, name).o_clk.eq(ClockSignal("dramsync")),
                getattr(self.pads, name).o_fclk.eq(ClockSignal("sync2x")),
            ]
            for i in range(len(getattr(self.pads, name).o0)):
                m.d.comb += [
                    getattr(self.pads, name).o0[i].eq(getattr(dfi.phases[0], name)[i]),
                    getattr(self.pads, name).o1[i].eq(getattr(dfi.phases[0], name)[i]),
                    getattr(self.pads, name).o2[i].eq(getattr(dfi.phases[1], name)[i]),
                    getattr(self.pads, name).o3[i].eq(getattr(dfi.phases[1], name)[i]),
                ]

        # DQ ---------------------------------------------------------------------------------------
        dq_oe = Signal()
        dqs_re = Signal()
        dqs_oe = Signal()
        dqs_postamble = Signal()
        dqs_preamble = Signal()
        for i in range(databits//8):
            # DQSBUFM
            dqs_i = Signal()
            dqsr90 = Signal()
            dqsw270 = Signal()
            dqsw = Signal()
            rdpntr = Signal(3)
            wrpntr = Signal(3)
            burstdet = Signal()
            datavalid = Signal()
            datavalid_prev = Signal()
            m.d.sync += datavalid_prev.eq(datavalid)

            m.submodules += Instance("DQSBUFM",
                p_DQS_LI_DEL_ADJ="MINUS",
                p_DQS_LI_DEL_VAL=1,
                p_DQS_LO_DEL_ADJ="MINUS",
                p_DQS_LO_DEL_VAL=4,

                # Delay
                i_DYNDELAY0=0,
                i_DYNDELAY1=0,
                i_DYNDELAY2=0,
                i_DYNDELAY3=0,
                i_DYNDELAY4=0,
                i_DYNDELAY5=0,
                i_DYNDELAY6=0,
                i_DYNDELAY7=0,

                # Clocks / Reset
                i_SCLK=ClockSignal("sync"),
                i_ECLK=ClockSignal("sync2x"),
                i_RST=ResetSignal("dramsync"),
                i_DDRDEL=init.delay,
                i_PAUSE=init.pause | self.rdly[i].w_stb,

                # Control
                # Assert LOADNs to use DDRDEL control
                i_RDLOADN=0,
                i_RDMOVE=0,
                i_RDDIRECTION=1,
                i_WRLOADN=0,
                i_WRMOVE=0,
                i_WRDIRECTION=1,

                # Reads (generate shifted DQS clock for reads)
                i_READ0=dqs_re,
                i_READ1=dqs_re,
                i_READCLKSEL0=self.rdly[i].w_data[0],
                i_READCLKSEL1=self.rdly[i].w_data[1],
                i_READCLKSEL2=self.rdly[i].w_data[2],
                i_DQSI=dqs_i,
                o_DQSR90=dqsr90,
                o_RDPNTR0=rdpntr[0],
                o_RDPNTR1=rdpntr[1],
                o_RDPNTR2=rdpntr[2],
                o_WRPNTR0=wrpntr[0],
                o_WRPNTR1=wrpntr[1],
                o_WRPNTR2=wrpntr[2],
                o_BURSTDET=burstdet,
                o_DATAVALID=datavalid,

                # Writes (generate shifted ECLK clock for writes)
                o_DQSW270=dqsw270,
                o_DQSW=dqsw)

            with m.If(burstdet):
                m.d.sync += burstdet_reg[i].eq(1)

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

            with m.If(bl8_chunk):
                m.d.sync += dm_o_data_muxed.eq(dm_o_data_d[4:])
            with m.Else():
                m.d.sync += dm_o_data_muxed.eq(dm_o_data[:4])

            m.submodules += Instance("ODDRX2DQA",
                i_RST=ResetSignal("dramsync"),
                i_ECLK=ClockSignal("sync2x"),
                i_SCLK=ClockSignal("dramsync"),
                i_DQSW270=dqsw270,
                i_D0=dm_o_data_muxed[0],
                i_D1=dm_o_data_muxed[1],
                i_D2=dm_o_data_muxed[2],
                i_D3=dm_o_data_muxed[3],
                o_Q=self.pads.dm.o[i])

            dqs = Signal()
            dqs_oe_n = Signal()
            m.submodules += [
                Instance("ODDRX2DQSB",
                    i_RST=ResetSignal("dramsync"),
                    i_ECLK=ClockSignal("sync2x"),
                    i_SCLK=ClockSignal(),
                    i_DQSW=dqsw,
                    i_D0=0,
                    i_D1=1,
                    i_D2=0,
                    i_D3=1,
                    o_Q=dqs),
                Instance("TSHX2DQSA",
                    i_RST=ResetSignal("dramsync"),
                    i_ECLK=ClockSignal("sync2x"),
                    i_SCLK=ClockSignal(),
                    i_DQSW=dqsw,
                    i_T0=~(dqs_oe | dqs_postamble),
                    i_T1=~(dqs_oe | dqs_preamble),
                    o_Q=dqs_oe_n),
                Instance("BB",
                    i_I=dqs,
                    i_T=dqs_oe_n,
                    o_O=dqs_i,
                    io_B=self.pads.dqs.p[i]),
            ]

            for j in range(8*i, 8*(i+1)):
                dq_o = Signal()
                dq_i = Signal()
                dq_oe_n = Signal()
                dq_i_delayed = Signal()
                dq_i_data = Signal(4)
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
                with m.If(bl8_chunk):
                    m.d.sync += dq_o_data_muxed.eq(dq_o_data_d[4:])
                with m.Else():
                    m.d.sync += dq_o_data_muxed.eq(dq_o_data[:4])

                m.submodules += [
                    Instance("ODDRX2DQA",
                        i_RST=ResetSignal("dramsync"),
                        i_ECLK=ClockSignal("sync2x"),
                        i_SCLK=ClockSignal(),
                        i_DQSW270=dqsw270,
                        i_D0=dq_o_data_muxed[0],
                        i_D1=dq_o_data_muxed[1],
                        i_D2=dq_o_data_muxed[2],
                        i_D3=dq_o_data_muxed[3],
                        o_Q=dq_o),
                    Instance("DELAYF",
                        p_DEL_MODE="DQS_ALIGNED_X2",
                        i_LOADN=1,
                        i_MOVE=0,
                        i_DIRECTION=0,
                        i_A=dq_i,
                        o_Z=dq_i_delayed),
                    Instance("IDDRX2DQA",
                        i_RST=ResetSignal("dramsync"),
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
                        o_Q0=dq_i_data[0],
                        o_Q1=dq_i_data[1],
                        o_Q2=dq_i_data[2],
                        o_Q3=dq_i_data[3]),
                ]
                m.submodules += [
                    Instance("TSHX2DQA",
                        i_RST=ResetSignal("dramsync"),
                        i_ECLK=ClockSignal("sync2x"),
                        i_SCLK=ClockSignal(),
                        i_DQSW270=dqsw270,
                        i_T0=~dq_oe,
                        i_T1=~dq_oe,
                        o_Q=dq_oe_n),
                    Instance("BB",
                        i_I=dq_o,
                        i_T=dq_oe_n,
                        o_O=dq_i,
                        io_B=self.pads.dq.io[j])
                ]
                with m.If(~datavalid_prev & datavalid):
                    m.d.sync += [
                        dfi.phases[0].rddata[0*databits+j].eq(dq_i_data[0]),
                        dfi.phases[0].rddata[1*databits+j].eq(dq_i_data[1]),
                        dfi.phases[0].rddata[2*databits+j].eq(dq_i_data[2]),
                        dfi.phases[0].rddata[3*databits+j].eq(dq_i_data[3]),
                    ]
                with m.Elif(datavalid):
                    m.d.sync += [
                        dfi.phases[1].rddata[0*databits+j].eq(dq_i_data[0]),
                        dfi.phases[1].rddata[1*databits+j].eq(dq_i_data[1]),
                        dfi.phases[1].rddata[2*databits+j].eq(dq_i_data[2]),
                        dfi.phases[1].rddata[3*databits+j].eq(dq_i_data[3]),
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
        rddata_en = Signal(self.settings.read_latency)
        rddata_en_last = Signal.like(rddata_en)
        m.d.comb += rddata_en.eq(Cat(dfi.phases[self.settings.rdphase].rddata_en, rddata_en_last))
        m.d.sync += rddata_en_last.eq(rddata_en)
        m.d.comb += dqs_re.eq(rddata_en[cl_sys_latency + 0] | rddata_en[cl_sys_latency + 1] | rddata_en[cl_sys_latency + 2])

        rddata_valid = Signal()
        m.d.sync += rddata_valid.eq(datavalid_prev & ~datavalid)
        for phase in dfi.phases:
            m.d.comb += phase.rddata_valid.eq(rddata_valid)

        # Write Control Path -----------------------------------------------------------------------
        # Creates a shift register of write commands coming from the DFI interface. This shift register
        # is used to control DQ/DQS tristates and to select write data of the DRAM burst from the DFI
        # interface: The PHY is operating in halfrate mode (so provide 4 datas every sys_clk cycles:
        # 2x for DDR, 2x for halfrate) but DDR3 requires a burst of 8 datas (BL8) for best efficiency.
        # Writes are then performed in 2 sys_clk cycles and data needs to be selected for each cycle.
        # FIXME: understand +2
        wrdata_en = Signal(cwl_sys_latency + 4)
        wrdata_en_last = Signal.like(wrdata_en)
        m.d.comb += wrdata_en.eq(Cat(dfi.phases[self.settings.wrphase].wrdata_en, wrdata_en_last))
        m.d.sync += wrdata_en_last.eq(wrdata_en)
        m.d.comb += dq_oe.eq(wrdata_en[cwl_sys_latency + 1] | wrdata_en[cwl_sys_latency + 2])
        m.d.comb += bl8_chunk.eq(wrdata_en[cwl_sys_latency + 1])
        m.d.comb += dqs_oe.eq(dq_oe)

        # Write DQS Postamble/Preamble Control Path ------------------------------------------------
        # Generates DQS Preamble 1 cycle before the first write and Postamble 1 cycle after the last
        # write. During writes, DQS tristate is configured as output for at least 4 sys_clk cycles:
        # 1 for Preamble, 2 for the Write and 1 for the Postamble.
        m.d.comb += dqs_preamble.eq(wrdata_en[cwl_sys_latency + 0] & ~wrdata_en[cwl_sys_latency + 1])
        m.d.comb += dqs_postamble.eq(wrdata_en[cwl_sys_latency + 3] & ~wrdata_en[cwl_sys_latency + 2])

        return m
