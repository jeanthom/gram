from nmigen import *

__ALL__ = ["delayed_enter", "RoundRobin", "Timeline"]

def delayed_enter(m, src, dst, delay):
    assert delay > 0

    for i in range(delay):
        if i == 0:
            statename = src
        else:
            statename = "{}-{}".format(src, i)

        if i == delay-1:
            deststate = dst
        else:
            deststate = "{}-{}".format(src, i+1)

        with m.State(statename):
            m.next = deststate

(SP_WITHDRAW, SP_CE) = range(2)

class RoundRobin(Elaboratable):
    def __init__(self, n, switch_policy=SP_WITHDRAW):
        self.request = Signal(n)
        self.grant = Signal(max=max(2, n))
        self.switch_policy = switch_policy
        if self.switch_policy == SP_CE:
            self.ce = Signal()

    def elaborate(self, platform):
        m = Module()

        # TODO: fix

        if n > 1:
            cases = {}
            for i in range(n):
                switch = []
                for j in reversed(range(i+1, i+n)):
                    t = j % n
                    switch = [
                        If(self.request[t],
                            self.grant.eq(t)
                        ).Else(
                            *switch
                        )
                    ]
                if self.switch_policy == SP_WITHDRAW:
                    case = [If(~self.request[i], *switch)]
                else:
                    case = switch
                cases[i] = case
            statement = Case(self.grant, cases)
            if self.switch_policy == SP_CE:
                with m.If(self.ce):
                    m.d.sync += statement
            else:
                m.d.sync += statement
        else:
            m.d.comb += self.grant.eq(0)

        return m

class Timeline(Elaboratable):
    def __init__(self, events):
        self.trigger = Signal()
        self._events = events

    def elaborate(self, platform):
        m = Module()

        lastevent = max([e[0] for e in self._events])
        counter = Signal(range(lastevent+1))

        # Counter incrementation
        # (with overflow handling)
        if (lastevent & (lastevent + 1)) != 0:
            with m.If(counter == lastevent):
                m.d.sync += counter.eq(0)
            with m.Else():
                with m.If(counter != 0):
                    m.d.sync += counter.eq(counter+1)
                with m.Elif(self.trigger):
                    m.d.sync += counter.eq(1)
        else:
            with m.If(counter != 0):
                m.d.sync += counter.eq(counter+1)
            with m.Elif(self.trigger):
                m.d.sync += counter.eq(1)

        for e in self._events:
            if e[0] == 0:
                with m.If(self.trigger & (counter == 0)):
                    m.d.sync += e[1]
            else:
                with m.If(counter == e[0]):
                    m.d.sync += e[1]

        return m
