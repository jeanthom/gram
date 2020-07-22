from nmigen import *
from nmigen.lib.io import pin_layout
from nmigen_soc import wishbone
from nmigen_stdio.serial import AsyncSerial, AsyncSerialTX
from nmigen.back.pysim import *

import unittest

__ALL__ = ["UARTBridge"]

class UARTBridge(Elaboratable):
    def __init__(self, divisor, pins):
        self.bus = wishbone.Interface(addr_width=30,
                                      data_width=32, granularity=8)
        self._pins = pins
        self._divisor = divisor

    def elaborate(self, platform):
        m = Module()

        m.submodules.serial = serial = AsyncSerial(divisor=self._divisor, pins=self._pins)

        address_width = 32
        data_width = 32

        cmd = Signal(8)
        length = Signal(8)
        address = Signal(address_width)
        data = Signal(data_width)
        bytes_count = Signal(range(data_width//8))
        words_count = Signal(8)

        m.d.comb += [
            self.bus.dat_w.eq(data),
            self.bus.adr.eq(address),
        ]

        with m.FSM():
            with m.State("Receive-Cmd"):
                m.d.comb += serial.rx.ack.eq(1)

                # Reset registers
                m.d.sync += [
                    bytes_count.eq(data_width//8-1),
                    words_count.eq(0),
                ]

                with m.If(serial.rx.rdy):
                    m.d.sync += cmd.eq(serial.rx.data)
                    m.next = "Receive-Length"

            with m.State("Receive-Length"):
                m.d.comb += serial.rx.ack.eq(1)

                with m.If(serial.rx.rdy):
                    m.d.sync += length.eq(serial.rx.data)
                    m.next = "Receive-Address"

            with m.State("Receive-Address"):
                m.d.comb += serial.rx.ack.eq(1)

                with m.If(serial.rx.rdy):
                    m.d.sync += [
                        address.eq(Cat(serial.rx.data, address)),
                        bytes_count.eq(bytes_count-1),
                    ]

                    with m.If(bytes_count == 0):
                        with m.Switch(cmd):
                            with m.Case(0x01):
                                m.next = "Handle-Write"
                            with m.Case(0x02):
                                m.next = "Handle-Read"
                            with m.Case():
                                m.next = "Receive-Cmd"

            with m.State("Handle-Write"):
                m.d.comb += serial.rx.ack.eq(1)

                with m.If(serial.rx.rdy):
                    m.d.sync += [
                        data.eq(Cat(serial.rx.data, data)),
                        bytes_count.eq(bytes_count-1),
                    ]
                    with m.If(bytes_count == 0):
                        m.next = "Write-Data"

            with m.State("Write-Data"):
                m.d.comb += [
                    self.bus.stb.eq(1),
                    self.bus.we.eq(1),
                    self.bus.cyc.eq(1),
                    self.bus.sel.eq(0xF),
                ]

                with m.If(self.bus.ack):
                    m.next = "Receive-Cmd"


            with m.State("Handle-Read"):
                m.d.comb += [
                    self.bus.stb.eq(1),
                    self.bus.we.eq(0),
                    self.bus.cyc.eq(1),
                    self.bus.sel.eq(0xF),
                ]

                with m.If(self.bus.ack):
                    m.d.sync += [
                        bytes_count.eq(data_width//8-1),
                        data.eq(self.bus.dat_r),
                    ]
                    m.next = "Send-Data"

            with m.State("Send-Data"):
                m.d.comb += serial.tx.ack.eq(1)

                with m.Switch(bytes_count):
                    for i in range(data_width//8):
                        with m.Case(i):
                            m.d.comb += serial.tx.data.eq(data[i*8:(i+1)*8])

                with m.If(serial.tx.rdy):
                    m.next = "Send-Data-Wait"

            with m.State("Send-Data-Wait"):
                with m.If(serial.tx.rdy):
                    m.d.sync += [
                        bytes_count.eq(bytes_count-1),
                    ]

                    with m.If(bytes_count == 0):
                        m.next = "Receive-Cmd"
                    with m.Else():
                        m.next = "Send-Data"

        return m

def serial_write(serial, val):
    while not (yield serial.tx.rdy):
        yield

    yield serial.tx.data.eq(val)
    yield serial.tx.ack.eq(1)
    yield

    while (yield serial.tx.rdy):
        yield

    yield serial.tx.ack.eq(0)

    while not (yield serial.tx.rdy):
        yield

    yield

def serial_read(serial):
    yield serial.rx.ack.eq(1)

    while not (yield serial.rx.rdy):
        yield

    data = (yield serial.rx.data)
    yield serial.rx.ack.eq(0)

    while (yield serial.rx.rdy):
        yield

    return data

class UARTBridgeTestCase(unittest.TestCase):
    # Minimum 5, lowest makes the simulation faster
    divisor = 5
    timeout = 10000

    def test_read(self):
        pins = Record([("rx", pin_layout(1, dir="i")),
                       ("tx", pin_layout(1, dir="o"))])
        dut = UARTBridge(divisor=self.divisor, pins=pins)
        serial = AsyncSerial(divisor=self.divisor)
        m = Module()
        m.submodules.bridge = dut
        m.submodules.serial = serial
        m.d.comb += [
            pins.rx.i.eq(serial.tx.o),
            serial.rx.i.eq(pins.tx.o),
        ]

        def process():
            # Send read command
            yield from serial_write(serial, 0x02)
            yield

            # Length = 1
            yield from serial_write(serial, 0x01)
            yield

            # Send 0x4000 as address
            yield from serial_write(serial, 0x00)
            yield
            yield from serial_write(serial, 0x00)
            yield
            yield from serial_write(serial, 0x40)
            yield
            yield from serial_write(serial, 0x00)
            yield
            
            # Handle wishbone request
            timeout = 0
            while not (yield dut.bus.cyc):
                yield
                timeout += 1
                if timeout > self.timeout:
                    raise RuntimeError("Simulation timed out")

            # Ensure Wishbone address is the one we asked for
            self.assertEqual((yield dut.bus.adr), 0x00004000)
            self.assertFalse((yield dut.bus.we))
            
            # Answer
            yield dut.bus.dat_r.eq(0x0DEFACED)
            yield dut.bus.ack.eq(1)
            yield

            # Check response on UART
            rx = yield from serial_read(serial)
            self.assertEqual(rx, 0x0D)
            rx = yield from serial_read(serial)
            self.assertEqual(rx, 0xEF)
            rx = yield from serial_read(serial)
            self.assertEqual(rx, 0xAC)
            rx = yield from serial_read(serial)
            self.assertEqual(rx, 0xED)            

            yield

        sim = Simulator(m)
        with sim.write_vcd("test_uartbridge.vcd"):
            sim.add_clock(1e-6)
            sim.add_sync_process(process)
            sim.run()

    def test_write(self):
        pins = Record([("rx", pin_layout(1, dir="i")),
                       ("tx", pin_layout(1, dir="o"))])
        dut = UARTBridge(divisor=self.divisor, pins=pins)
        serial = AsyncSerial(divisor=self.divisor)
        m = Module()
        m.submodules.bridge = dut
        m.submodules.serial = serial
        m.d.comb += [
            pins.rx.i.eq(serial.tx.o),
            serial.rx.i.eq(pins.tx.o),
        ]

        def process():
            # Send write command
            yield from serial_write(serial, 0x01)
            yield

            # Length = 1
            yield from serial_write(serial, 0x01)
            yield

            # Send 0x4000 as address
            yield from serial_write(serial, 0x00)
            yield
            yield from serial_write(serial, 0x00)
            yield
            yield from serial_write(serial, 0x40)
            yield
            yield from serial_write(serial, 0x00)
            yield

            # Send 0xFEEDFACE as value
            yield from serial_write(serial, 0xFE)
            yield
            yield from serial_write(serial, 0xED)
            yield
            yield from serial_write(serial, 0xFA)
            yield
            yield from serial_write(serial, 0xCE)
            
            # Handle wishbone request
            timeout = 0
            while not (yield dut.bus.cyc):
                yield
                timeout += 1
                if timeout > self.timeout:
                    raise RuntimeError("Simulation timed out")

            # Ensure Wishbone address is the one we asked for
            self.assertEqual((yield dut.bus.adr), 0x00004000)
            self.assertEqual((yield dut.bus.dat_w), 0xFEEDFACE)
            self.assertTrue((yield dut.bus.we))
            
            # Answer
            yield dut.bus.ack.eq(1)
            yield

        sim = Simulator(m)
        with sim.write_vcd("test_uartbridge.vcd"):
            sim.add_clock(1e-6)
            sim.add_sync_process(process)
            sim.run()
