# This file is Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2020 Antmicro <www.antmicro.com>
# License: BSD

# SDRAM simulation PHY at DFI level tested with SDR/DDR/DDR2/LPDDR/DDR3
# TODO:
# - add multirank support.

from nmigen import *
from nmigen.utils import log2_int

from gram.common import burst_lengths
from gram.phy.dfi import *
from gram.modules import _speedgrade_timings, _technology_timings

from functools import reduce
from operator import or_

import struct

SDRAM_VERBOSE_OFF = 0
SDRAM_VERBOSE_STD = 1
SDRAM_VERBOSE_DBG = 2

def Display(*args):
    return Signal().eq(0)

def Assert(*args):
    return Signal().eq(0)

# Bank Model ---------------------------------------------------------------------------------------

class BankModel(Elaboratable):
    def __init__(self, data_width, nrows, ncols, burst_length, nphases, we_granularity, init):
        self.activate     = Signal()
        self.activate_row = Signal(range(nrows))
        self.precharge    = Signal()

        self.write        = Signal()
        self.write_col    = Signal(range(ncols))
        self.write_data   = Signal(data_width)
        self.write_mask   = Signal(data_width//8)

        self.read         = Signal()
        self.read_col     = Signal(range(ncols))
        self.read_data    = Signal(data_width)
        self.nphases = nphases
        self.nrows = nrows
        self.ncols = ncols
        self.burst_length = burst_length
        self.data_width = data_width
        self.we_granularity = we_granularity
        self.init = init

    def elaborate(self, platform):
        m = Module()

        nrows = self.nrows
        ncols = self.ncols
        burst_length = self.burst_length
        data_width = self.data_width
        we_granularity = self.we_granularity
        init = self.init

        active = Signal()
        row    = Signal(range(nrows))

        with m.If(self.precharge):
            m.d.sync += active.eq(0)
        with m.Elif(self.activate):
            m.d.sync += [
                active.eq(1),
                row.eq(self.activate_row),
            ]

        bank_mem_len   = nrows*ncols//(burst_length*self.nphases)
        # mem            = Memory(width=data_width, depth=bank_mem_len, init=init)
        # write_port     = mem.get_port(write_capable=True, we_granularity=we_granularity)
        # read_port      = mem.get_port(async_read=True)
        # m.submodules += mem, read_port, write_port

        wraddr         = Signal(range(bank_mem_len))
        rdaddr         = Signal(range(bank_mem_len))

        m.d.comb += [
            wraddr.eq((row*ncols | self.write_col)[log2_int(burst_length*self.nphases):]),
            rdaddr.eq((row*ncols | self.read_col)[log2_int(burst_length*self.nphases):]),
        ]

        with m.If(active):
            # m.d.comb += [
            #     write_port.adr.eq(wraddr),
            #     write_port.dat_w.eq(self.write_data),
            # ]

            # with m.If(we_granularity):
            #     m.d.comb += write_port.we.eq(Replicate(self.write, data_width//8) & ~self.write_mask)
            # with m.Else():
            #     m.d.comb += write_port.we.eq(self.write)

            with m.If(self.read):
                # m.d.comb += [
                #     read_port.adr.eq(rdaddr),
                #     self.read_data.eq(read_port.dat_r),
                # ]
                m.d.comb += self.read_data.eq(0xDEADBEEF)

        return m

# DFI Phase Model ----------------------------------------------------------------------------------

class DFIPhaseModel(Elaboratable):
    def __init__(self, dfi, n):
        self.phase = dfi.phases[n]

        self.bank         = self.phase.bank
        self.address      = self.phase.address

        self.wrdata       = self.phase.wrdata
        self.wrdata_mask  = self.phase.wrdata_mask

        self.rddata       = self.phase.rddata
        self.rddata_valid = self.phase.rddata_valid

        self.activate     = Signal()
        self.precharge    = Signal()
        self.write        = Signal()
        self.read         = Signal()

    def elaborate(self, platform):
        m = Module()

        with m.If(~self.phase.cs_n & ~self.phase.ras_n & self.phase.cas_n):
            m.d.comb += [
                self.activate.eq(self.phase.we_n),
                self.precharge.eq(~self.phase.we_n),
            ]

        with m.If(~self.phase.cs_n & self.phase.ras_n & ~self.phase.cas_n):
            m.d.comb += [
                self.write.eq(~self.phase.we_n),
                self.read.eq(self.phase.we_n),
            ]

        return m

# DFI Timings Checker ------------------------------------------------------------------------------

class SDRAMCMD:
    def __init__(self, name: str, enc: int, idx: int):
        self.name = name
        self.enc  = enc
        self.idx  = idx


class TimingRule:
    def __init__(self, prev: str, curr: str, delay: int):
        self.name  = prev + "->" + curr
        self.prev  = prev
        self.curr  = curr
        self.delay = delay


class DFITimingsChecker(Elaboratable):
    CMDS = [
        # Name, cs & ras & cas & we value
        ("PRE",  "0010"), # Precharge
        ("REF",  "0001"), # Self refresh
        ("ACT",  "0011"), # Activate
        ("RD",   "0101"), # Read
        ("WR",   "0100"), # Write
        ("ZQCS", "0110"), # ZQCS
    ]

    RULES = [
        # tRP
        ("PRE",  "ACT", "tRP"),
        ("PRE",  "REF", "tRP"),
        # tRCD
        ("ACT",  "WR",  "tRCD"),
        ("ACT",  "RD",  "tRCD"),
        # tRAS
        ("ACT",  "PRE", "tRAS"),
        # tRFC
        ("REF",  "PRE", "tRFC"),
        ("REF",  "ACT", "tRFC"),
        # tCCD
        ("WR",   "RD",  "tCCD"),
        ("WR",   "WR",  "tCCD"),
        ("RD",   "RD",  "tCCD"),
        ("RD",   "WR",  "tCCD"),
        # tRC
        ("ACT",  "ACT", "tRC"),
        # tWR
        ("WR",   "PRE", "tWR"),
        # tWTR
        ("WR",   "RD",  "tWTR"),
        # tZQCS
        ("ZQCS", "ACT", "tZQCS"),
    ]

    def add_cmds(self):
        self.cmds = {}
        for idx, (name, pattern) in enumerate(self.CMDS):
            self.cmds[name] = SDRAMCMD(name, int(pattern, 2), idx)

    def add_rule(self, prev, curr, delay):
        if not isinstance(delay, int):
            delay = self.timings[delay]
        self.rules.append(TimingRule(prev, curr, delay))

    def add_rules(self):
        self.rules = []
        for rule in self.RULES:
            self.add_rule(*rule)

    # Convert ns to ps
    def ns_to_ps(self, val):
        return int(val * 1e3)

    def ck_ns_to_ps(self, val, tck):
        c, t = val
        c = 0 if c is None else c * tck
        t = 0 if t is None else t
        return self.ns_to_ps(max(c, t))

    def prepare_timings(self, timings, refresh_mode, memtype):
        CK_NS = ["tRFC", "tWTR", "tFAW", "tCCD", "tRRD", "tZQCS"]
        REF   = ["tREFI", "tRFC"]
        self.timings = timings
        new_timings  = {}

        tck = self.timings["tCK"]

        for key, val in self.timings.items():
            if refresh_mode is not None and key in REF:
                val = val[refresh_mode]

            if val is None:
                val = 0
            elif key in CK_NS:
                val = self.ck_ns_to_ps(val, tck)
            else:
                val = self.ns_to_ps(val)

            new_timings[key] = val

        new_timings["tRC"] = new_timings["tRAS"] + new_timings["tRP"]

        # Adjust timings relative to write burst - tWR & tWTR
        wrburst = burst_lengths[memtype] if memtype == "SDR" else burst_lengths[memtype] // 2
        wrburst = (new_timings["tCK"] * (wrburst - 1))
        new_timings["tWR"]  = new_timings["tWR"]  + wrburst
        new_timings["tWTR"] = new_timings["tWTR"] + wrburst

        self.timings = new_timings

    def __init__(self, dfi, nbanks, nphases, timings, refresh_mode, memtype, verbose=False):
        self.prepare_timings(timings, refresh_mode, memtype)
        self.add_cmds()
        self.add_rules()
        self.nphases = nphases
        self.nbanks = nbanks
        self.dfi = dfi
        self.timings = timings
        self.refresh_mode = refresh_mode
        self.memtype = memtype
        self.verbose = verbose

    def elaborate(self, platform):
        m = Module()

        cnt = Signal(64)
        m.d.sync += cnt.eq(cnt+self.nphases)

        phases = self.dfi.phases
        nbanks = self.nbanks
        timings = self.timings
        refresh_mode = self.refresh_mode
        memtype = self.memtype
        verbose = self.verbose

        last_cmd_ps = [[Signal.like(cnt) for _ in range(len(self.cmds))] for _ in range(nbanks)]
        last_cmd    = [Signal(4) for i in range(nbanks)]

        act_ps   = Array([Signal().like(cnt) for i in range(4)])
        act_curr = Signal(range(4))

        ref_issued = Signal(self.nphases)

        for np, phase in enumerate(phases):
            ps = Signal().like(cnt)
            m.d.comb += ps.eq((cnt + np)*int(self.timings["tCK"]))
            state = Signal(4)
            m.d.comb += state.eq(Cat(phase.we_n, phase.cas_n, phase.ras_n, phase.cs_n))
            all_banks = Signal()

            m.d.comb += all_banks.eq(
                (self.cmds["REF"].enc == state) |
                ((self.cmds["PRE"].enc == state) & phase.address[10])
            )

            # tREFI
            m.d.comb += ref_issued[np].eq(self.cmds["REF"].enc == state)

            # Print debug information
            # TODO: find a way to bring back logging
            # if verbose:
            #     for _, cmd in self.cmds.items():
            #         self.sync += [
            #             If(state == cmd.enc,
            #                 If(all_banks,
            #                     Display("[%016dps] P%0d " + cmd.name, ps, np)
            #                 ).Else(
            #                     Display("[%016dps] P%0d B%0d " + cmd.name, ps, np, phase.bank)
            #                 )
            #             )
            #         ]

            # Bank command monitoring
            for i in range(nbanks):
                for _, curr in self.cmds.items():
                    cmd_recv = Signal()
                    m.d.comb += cmd_recv.eq(((phase.bank == i) | all_banks) & (state == curr.enc))

                    # Checking rules from self.rules
                    for _, prev in self.cmds.items():
                        for rule in self.rules:
                            if rule.prev == prev.name and rule.curr == curr.name:
                                # Display("[%016dps] {} violation on bank %0d".format(rule.name), ps, i)
                                m.d.sync += Assert(~(cmd_recv & (last_cmd[i] == prev.enc) & (ps < (last_cmd_ps[i][prev.idx] + rule.delay))))

                    # Save command timestamp in an array
                    with m.If(cmd_recv):
                        m.d.comb += [
                            last_cmd_ps[i][curr.idx].eq(ps),
                            last_cmd[i].eq(state),
                        ]

                    # tRRD & tFAW
                    if curr.name == "ACT":
                        act_next = Signal().like(act_curr)
                        m.d.comb += act_next.eq(act_curr+1)

                        # act_curr points to newest ACT timestamp
                        #Display("[%016dps] tRRD violation on bank %0d", ps, i)
                        #m.d.sync += Assert(~(cmd_recv & (ps < (act_ps[act_curr] + int(self.timings["tRRD"])))))

                        # act_next points to the oldest ACT timestamp
                        #Display("[%016dps] tFAW violation on bank %0d", ps, i)
                        #m.d.sync += Assert(~(cmd_recv & (ps < (act_ps[act_next] + int(self.timings["tFAW"])))))

                        # Save ACT timestamp in a circular buffer
                        with m.If(cmd_recv):
                            m.d.sync += [
                                act_ps[act_next].eq(ps),
                                act_curr.eq(act_next),
                            ]

        # tREFI
        ref_ps      = Signal().like(cnt)
        ref_ps_mod  = Signal().like(cnt)
        ref_ps_diff = Signal(signed(64))
        curr_diff   = Signal().like(ref_ps_diff)

        m.d.comb += curr_diff.eq(ps - (ref_ps + int(self.timings["tREFI"])))

        # Work in 64ms periods
        with m.If(ref_ps_mod < int(64e9)):
            m.d.sync += ref_ps_mod.eq(ref_ps_mod + int(self.nphases * self.timings["tCK"]))
        with m.Else():
            m.d.sync += ref_ps_mod.eq(0)

        # Update timestamp and difference
        with m.If(ref_issued != 0):
            m.d.sync += [
                ref_ps.eq(ps),
                ref_ps_diff.eq(ref_ps_diff - curr_diff),
            ]

        #Display("[%016dps] tREFI violation (64ms period): %0d", ps, ref_ps_diff)
        m.d.sync += Assert(~((ref_ps_mod == 0) & (ref_ps_diff > 0)))

        # Report any refresh periods longer than tREFI
        # TODO: find a way to bring back logging
        # if verbose:
        #     ref_done = Signal()
        #     self.sync += [
        #         If(ref_issued != 0,
        #             ref_done.eq(1),
        #             If(~ref_done,
        #                 Display("[%016dps] Late refresh", ps)
        #             )
        #         )
        #     ]

        #     self.sync += [
        #         If((curr_diff > 0) & ref_done & (ref_issued == 0),
        #             Display("[%016dps] tREFI violation", ps),
        #             ref_done.eq(0)
        #         )
        #     ]

        # There is a maximum delay between refreshes on >=DDR
        ref_limit = {"1x": 9, "2x": 17, "4x": 36}
        if memtype != "SDR":
            refresh_mode = "1x" if refresh_mode is None else refresh_mode
            ref_done = Signal()
            with m.If(ref_issued != 0):
                m.d.sync += ref_done.eq(1)

            with m.If((ref_issued == 0) & ref_done &
                   (ref_ps > (ps + int(ref_limit[refresh_mode] * self.timings['tREFI'])))):
                m.d.sync += ref_done.eq(0)
            # self.sync += [
            #     If((ref_issued == 0) & ref_done &
            #        (ref_ps > (ps + ref_limit[refresh_mode] * self.timings['tREFI'])),
            #         Display("[%016dps] tREFI violation (too many postponed refreshes)", ps),
            #         ref_done.eq(0)
            #     )
            # ]

        return m

class FakePHY(Elaboratable):
    def __prepare_bank_init_data(self, init, nbanks, nrows, ncols, data_width, address_mapping):
        mem_size          = (self.settings.databits//8)*(nrows*ncols*nbanks)
        bank_size         = mem_size // nbanks
        column_size       = bank_size // nrows
        model_bank_size   = bank_size // (data_width//8)
        model_column_size = model_bank_size // nrows
        model_data_ratio  = data_width // 32
        data_width_bytes  = data_width // 8
        bank_init         = [[] for i in range(nbanks)]

        # Pad init if too short
        if len(init)%data_width_bytes != 0:
            init.extend([0]*(data_width_bytes-len(init)%data_width_bytes))


        # Convert init data width from 32-bit to data_width if needed
        if model_data_ratio > 1:
            new_init = [0]*(len(init)//model_data_ratio)
            for i in range(0, len(init), model_data_ratio):
                ints = init[i:i+model_data_ratio]
                strs = "".join("{:08x}".format(x) for x in reversed(ints))
                new_init[i//model_data_ratio] = int(strs, 16)
            init = new_init
        elif model_data_ratio == 0:
            assert data_width_bytes in [1, 2]
            model_data_ratio = 4 // data_width_bytes
            struct_unpack_patterns = {1: "4B", 2: "2H"}
            new_init = [0]*int(len(init)*model_data_ratio)
            for i in range(len(init)):
                new_init[model_data_ratio*i:model_data_ratio*(i+1)] = struct.unpack(
                    struct_unpack_patterns[data_width_bytes],
                    struct.pack("I", init[i])
                )[0:model_data_ratio]
            init = new_init

        if address_mapping == "ROW_BANK_COL":
            for row in range(nrows):
                for bank in range(nbanks):
                    start = (row*nbanks*model_column_size + bank*model_column_size)
                    end   = min(start + model_column_size, len(init))
                    if start > len(init):
                        break
                    bank_init[bank].extend(init[start:end])
        elif address_mapping == "BANK_ROW_COL":
            for bank in range(nbanks):
                start = bank*model_bank_size
                end   = min(start + model_bank_size, len(init))
                if start > len(init):
                    break
                bank_init[bank] = init[start:end]

        return bank_init

    def __init__(self, module, settings, clk_freq=100e6,
        we_granularity         = 8,
        init                   = [],
        address_mapping        = "ROW_BANK_COL",
        verbosity              = SDRAM_VERBOSE_OFF):

        # Parameters -------------------------------------------------------------------------------
        self.burst_length = {
            "SDR":   1,
            "DDR":   2,
            "LPDDR": 2,
            "DDR2":  2,
            "DDR3":  2,
            "DDR4":  2,
            }[settings.memtype]

        self.addressbits = module.geom_settings.addressbits
        self.bankbits = module.geom_settings.bankbits
        self.rowbits = module.geom_settings.rowbits
        self.colbits = module.geom_settings.colbits

        self.settings = settings
        self.module = module

        self.verbosity = verbosity
        self.clk_freq = clk_freq
        self.we_granularity = we_granularity

        self.init = init

        # DFI Interface ----------------------------------------------------------------------------
        self.dfi = Interface(
            addressbits = self.addressbits,
            bankbits    = self.bankbits,
            nranks      = self.settings.nranks,
            databits    = self.settings.dfi_databits,
            nphases     = self.settings.nphases
        )

    def elaborate(self, platform):
        m = Module()

        nphases    = self.settings.nphases
        nbanks     = 2**self.bankbits
        nrows      = 2**self.rowbits
        ncols      = 2**self.colbits
        data_width = self.settings.dfi_databits*self.settings.nphases

        # DFI phases -------------------------------------------------------------------------------
        phases = [DFIPhaseModel(self.dfi, n) for n in range(self.settings.nphases)]
        m.submodules += phases

        # DFI timing checker -----------------------------------------------------------------------
        if self.verbosity > SDRAM_VERBOSE_OFF:
            timings = {"tCK": (1e9 / self.clk_freq) / nphases}

            for name in _speedgrade_timings + _technology_timings:
                timings[name] = self.module.get(name)

            timing_checker = DFITimingsChecker(
                dfi          = self.dfi,
                nbanks       = nbanks,
                nphases      = nphases,
                timings      = timings,
                refresh_mode = self.module.timing_settings.fine_refresh_mode,
                memtype      = self.settings.memtype,
                verbose      = self.verbosity > SDRAM_VERBOSE_DBG)
            m.submodules += timing_checker

        # Bank init data ---------------------------------------------------------------------------
        bank_init  = [None for i in range(nbanks)]

        if self.init:
            bank_init = self.__prepare_bank_init_data(
                init            = self.init,
                nbanks          = nbanks,
                nrows           = nrows,
                ncols           = ncols,
                data_width      = data_width,
                address_mapping = address_mapping
            )

        # Banks ------------------------------------------------------------------------------------
        banks = [BankModel(
            data_width     = data_width,
            nrows          = nrows,
            ncols          = ncols,
            burst_length   = self.burst_length,
            nphases        = nphases,
            we_granularity = self.we_granularity,
            init           = bank_init[i]) for i in range(nbanks)]
        m.submodules += banks

        # Connect DFI phases to Banks (CMDs, Write datapath) ---------------------------------------
        for nb, bank in enumerate(banks):
            # Bank activate
            activates = Signal(len(phases))
            with m.Switch(activates):
                for np, phase in enumerate(phases):
                    m.d.comb += activates[np].eq(phase.activate)
                    with m.Case(2**np):
                        m.d.comb +=  [
                            bank.activate.eq(phase.bank == nb),
                            bank.activate_row.eq(phase.address)
                        ]

            # Bank precharge
            precharges = Signal(len(phases))
            with m.Switch(precharges):
                for np, phase in enumerate(phases):
                    m.d.comb += precharges[np].eq(phase.precharge)
                    with m.Case(2**np):
                        m.d.comb += bank.precharge.eq((phase.bank == nb) | phase.address[10])

            # Bank writes
            bank_write = Signal()
            bank_write_col = Signal(range(ncols))
            writes = Signal(len(phases))
            with m.Switch(writes):
                for np, phase in enumerate(phases):
                    m.d.comb += writes[np].eq(phase.write)
                    with m.Case(2**np):
                        m.d.comb += [
                            bank_write.eq(phase.bank == nb),
                            bank_write_col.eq(phase.address)
                        ]
            m.d.comb += [
                bank.write_data.eq(Cat(*[phase.wrdata for phase in phases])),
                bank.write_mask.eq(Cat(*[phase.wrdata_mask for phase in phases]))
            ]

            # Simulate write latency
            for i in range(self.settings.write_latency):
                new_bank_write     = Signal()
                new_bank_write_col = Signal(range(ncols))
                m.d.sync += [
                    new_bank_write.eq(bank_write),
                    new_bank_write_col.eq(bank_write_col)
                ]
                bank_write = new_bank_write
                bank_write_col = new_bank_write_col

            m.d.comb += [
                bank.write.eq(bank_write),
                bank.write_col.eq(bank_write_col)
            ]

            # Bank reads
            reads = Signal(len(phases))
            with m.Switch(reads):
                for np, phase in enumerate(phases):
                    m.d.comb += reads[np].eq(phase.read)
                    with m.Case(2**np):
                        m.d.comb += [
                            bank.read.eq(phase.bank == nb),
                            bank.read_col.eq(phase.address),
                        ]

        # Connect Banks to DFI phases (CMDs, Read datapath) ----------------------------------------
        banks_read      = Signal()
        banks_read_data = Signal(data_width)
        m.d.comb += [
            banks_read.eq(reduce(or_, [bank.read for bank in banks])),
            banks_read_data.eq(reduce(or_, [bank.read_data for bank in banks]))
        ]

        # Simulate read latency --------------------------------------------------------------------
        for i in range(self.settings.read_latency):
            new_banks_read      = Signal()
            new_banks_read_data = Signal(data_width)
            m.d.sync += [
                new_banks_read.eq(banks_read),
                new_banks_read_data.eq(banks_read_data)
            ]
            banks_read      = new_banks_read
            banks_read_data = new_banks_read_data

        m.d.comb += [
            Cat(*[phase.rddata_valid for phase in phases]).eq(banks_read),
            Cat(*[phase.rddata for phase in phases]).eq(banks_read_data)
        ]

        return m
