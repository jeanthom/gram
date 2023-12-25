# Copyright (c) 2020 LambdaConcept <contact@lambdaconcept.com>
# Copyright (c) 2021 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Copyright (c) 2018-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Michael Betz <michibetz@gmail.com>
#
# Based on code from LambaConcept, from the gram example which is BSD-2-License
# https://github.com/jeanthom/gram/tree/master/examples
#
# Modifications for the Libre-SOC Project funded by NLnet and NGI POINTER
# under EU Grants 871528 and 957073, under the LGPLv3+ License


from nmigen import (Elaboratable, Module, Signal, ClockDomain, Instance,
                    ClockSignal, ResetSignal, Const)

__all__ = ["ECP5CRG"]


class PLL(Elaboratable):
    nclkouts_max    = 3
    clki_div_range  = (1, 128+1)
    clkfb_div_range = (1, 128+1)
    clko_div_range  = (1, 128+1)
    clki_freq_range = (    8e6,  400e6)
    clko_freq_range = (3.125e6,  400e6)
    vco_freq_range  = (  400e6,  800e6)

    def __init__(self, clkin,
                       clksel=Signal(shape=2, reset=2),
                       reset=Signal(reset_less=True),
                       locked=Signal()):
        self.clkin = clkin
        self.clkin_freq = None
        self.clksel = clksel
        self.locked = locked
        self.reset  = reset
        self.nclkouts   = 0
        self.clkouts    = {}
        self.config     = {}
        self.params     = {}

    def ports(self):
        return [
            self.clkin,
            self.clksel,
            self.lock,
        ] + list(self.clkouts.values())

    def set_clkin_freq(self, freq):
        (clki_freq_min, clki_freq_max) = self.clki_freq_range
        assert freq >= clki_freq_min
        assert freq <= clki_freq_max
        self.clkin_freq = freq

    def create_clkout(self, cd, freq, phase=0, margin=1e-2):
        (clko_freq_min, clko_freq_max) = self.clko_freq_range
        assert freq >= clko_freq_min
        assert freq <= clko_freq_max
        assert self.nclkouts < self.nclkouts_max
        self.clkouts[self.nclkouts] = (cd, freq, phase, margin)
        #create_clkout_log(self.logger, cd.name, freq, margin, self.nclkouts)
        print("clock domain", cd.domain, freq, margin, self.nclkouts)
        self.nclkouts += 1

    def compute_config(self):
        config = {}
        for clki_div in range(*self.clki_div_range):
            config["clki_div"] = clki_div
            for clkfb_div in range(*self.clkfb_div_range):
                all_valid = True
                vco_freq = self.clkin_freq/clki_div*clkfb_div*1 # clkos3_div=1
                (vco_freq_min, vco_freq_max) = self.vco_freq_range
                if vco_freq >= vco_freq_min and vco_freq <= vco_freq_max:
                    for n, (clk, f, p, m) in sorted(self.clkouts.items()):
                        valid = False
                        for d in range(*self.clko_div_range):
                            clk_freq = vco_freq/d
                            if abs(clk_freq - f) <= f*m:
                                config["clko{}_freq".format(n)]  = clk_freq
                                config["clko{}_div".format(n)]   = d
                                config["clko{}_phase".format(n)] = p
                                valid = True
                                break
                        if not valid:
                            all_valid = False
                else:
                    all_valid = False
                if all_valid:
                    config["vco"] = vco_freq
                    config["clkfb_div"] = clkfb_div
                    #compute_config_log(self.logger, config)
                    print ("PLL config", config)
                    return config
        raise ValueError("No PLL config found")

    def elaborate(self, platform):
        config = self.compute_config()
        clkfb = Signal()
        self.params.update(
            # attributes
            a_FREQUENCY_PIN_CLKI     = str(self.clkin_freq/1e6),
            a_ICP_CURRENT            = "6",
            a_LPF_RESISTOR           = "16",
            a_MFG_ENABLE_FILTEROPAMP = "1",
            a_MFG_GMCREF_SEL         = "2",
            # parameters
            p_FEEDBK_PATH   = "INT_OS3", # CLKOS3 rsvd for feedback with div=1.
            p_CLKOS3_ENABLE = "ENABLED",
            p_CLKOS3_DIV    = 1,
            p_CLKFB_DIV     = config["clkfb_div"],
            p_CLKI_DIV      = config["clki_div"],
            # reset, input clock, lock-achieved output
            i_RST           = self.reset,
            i_CLKI          = self.clkin,
            o_LOCK          = self.locked,
        )
        # for each clock-out, set additional parameters
        for n, (clk, f, p, m) in sorted(self.clkouts.items()):
            n_to_l = {0: "P", 1: "S", 2: "S2"}
            div    = config["clko{}_div".format(n)]
            cphase = int(p*(div + 1)/360 + div)
            self.params["p_CLKO{}_ENABLE".format(n_to_l[n])] = "ENABLED"
            self.params["p_CLKO{}_DIV".format(n_to_l[n])]    = div
            self.params["p_CLKO{}_FPHASE".format(n_to_l[n])] = 0
            self.params["p_CLKO{}_CPHASE".format(n_to_l[n])] = cphase
            self.params["o_CLKO{}".format(n_to_l[n])]        = clk

        m = Module()
        print ("params", self.params)
        pll = Instance("EHXPLLL", **self.params)
        m.submodules.pll = pll
        return m

        pll = Instance("EHXPLLL",
                       p_OUTDIVIDER_MUXA='DIVA',
                       p_OUTDIVIDER_MUXB='DIVB',
                       p_CLKOP_ENABLE='ENABLED',
                       p_CLKOS_ENABLE='ENABLED',
                       p_CLKOS2_ENABLE='DISABLED',
                       p_CLKOS3_ENABLE='DISABLED',
                       p_CLKOP_DIV=self.CLKOP_DIV,
                       p_CLKOS_DIV=self.CLKOS_DIV,
                       p_CLKFB_DIV=self.CLKFB_DIV,
                       p_CLKI_DIV=self.CLKI_DIV,
                       p_FEEDBK_PATH='INT_OP',
                       p_CLKOP_TRIM_POL="FALLING",
                       p_CLKOP_TRIM_DELAY=0,
                       p_CLKOS_TRIM_POL="FALLING",
                       p_CLKOS_TRIM_DELAY=0,
                       i_CLKI=self.clkin,
                       i_RST=0,
                       i_STDBY=0,
                       i_PHASESEL0=0,
                       i_PHASESEL1=0,
                       i_PHASEDIR=0,
                       i_PHASESTEP=0,
                       i_PHASELOADREG=0,
                       i_PLLWAKESYNC=0,
                       i_ENCLKOP=1,
                       i_ENCLKOS=1,
                       i_ENCLKOS2=0,
                       i_ENCLKOS3=0,
                       o_CLKOP=self.clkout1,
                       o_CLKOS=self.clkout2,
                       o_CLKOS2=self.clkout3,
                       o_CLKOS3=self.clkout4,
                       o_LOCK=self.lock,
                       )


class ECP5CRG(Elaboratable):
    def __init__(self, sys_clk_freq=100e6, pod_bits=16):
        self.sys_clk_freq = sys_clk_freq
        self.pod_bits = pod_bits

        # DDR clock control signals
        self.ddr_clk_stop = Signal()
        self.ddr_clk_reset = Signal()

    def elaborate(self, platform):
        m = Module()

        # Get 100Mhz from oscillator
        extclk = platform.request(platform.default_clk)
        cd_rawclk = ClockDomain("rawclk", local=True, reset_less=True)
        m.d.comb += cd_rawclk.clk.eq(extclk)
        m.domains += cd_rawclk

        # Reset
        if platform.default_rst is not None:
            reset = platform.request(platform.default_rst).i
        else:
            reset = Const(0) # whoops

        gsr0 = Signal()
        gsr1 = Signal()

        m.submodules += [
            Instance("FD1S3AX", p_GSR="DISABLED",
                                i_CK=ClockSignal("rawclk"),
                                i_D=~reset,
                                o_Q=gsr0),
            Instance("FD1S3AX", p_GSR="DISABLED",
                                i_CK=ClockSignal("rawclk"),
                                i_D=gsr0,
                                o_Q=gsr1),
            Instance("SGSR", i_CLK=ClockSignal("rawclk"),
                             i_GSR=gsr1),
        ]

        # Power-on delay
        podcnt = Signal(self.pod_bits, reset=-1)
        pod_done = Signal()
        with m.If(podcnt != 0):
            m.d.rawclk += podcnt.eq(podcnt-1)
        m.d.rawclk += pod_done.eq(podcnt == 0)

        # PLL
        m.submodules.pll = pll = PLL(ClockSignal("rawclk"), reset=~pod_done|~reset)

        # Generating sync2x (200Mhz) and init (25Mhz) from extclk
        cd_sync2x = ClockDomain("sync2x", local=False)
        cd_sync2x_unbuf = ClockDomain("sync2x_unbuf",
                                      local=False, reset_less=True)
        cd_init = ClockDomain("init", local=False)
        cd_sync = ClockDomain("sync", local=False)
        cd_dramsync = ClockDomain("dramsync", local=False)

        # create PLL clocks
        pll.set_clkin_freq(platform.default_clk_frequency)
        pll.create_clkout(ClockSignal("sync2x_unbuf"), 2*self.sys_clk_freq)
        pll.create_clkout(ClockSignal("init"), 25e6)
        m.submodules += Instance("ECLKSYNCB",
                i_ECLKI = ClockSignal("sync2x_unbuf"),
                i_STOP  = self.ddr_clk_stop,
                o_ECLKO = ClockSignal("sync2x"))
        m.domains += cd_sync2x_unbuf
        m.domains += cd_sync2x
        m.domains += cd_init
        m.domains += cd_sync
        m.domains += cd_dramsync
        reset_ok = Signal(reset_less=True)
        m.d.comb += reset_ok.eq(~pll.locked|~pod_done)
        m.d.comb += ResetSignal("init").eq(reset_ok)
        m.d.comb += ResetSignal("sync").eq(reset_ok)
        m.d.comb += ResetSignal("dramsync").eq(reset_ok|self.ddr_clk_reset)

        # # Generating sync (100Mhz) from sync2x

        m.submodules += Instance("CLKDIVF",
            p_DIV="2.0",
            i_ALIGNWD=0,
            i_CLKI=ClockSignal("sync2x"),
            i_RST=ResetSignal("dramsync"),
            o_CDIVX=ClockSignal("sync"))

        # temporarily set dram sync clock exactly equal to main sync
        m.d.comb += ClockSignal("dramsync").eq(ClockSignal("sync"))

        return m

