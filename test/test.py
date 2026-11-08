# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from spi_mem_model import spi_mem
import hack_ops

PROGRAMS = Path(__file__).parent / "programs"


def load_hack(name):
    """Read an assembled .hack file (one 16-char binary line per instruction)
    into a {word address: instruction} dict for the ROM model."""
    lines = (PROGRAMS / name).read_text().split()
    return {addr: int(line, 2) for addr, line in enumerate(lines)}


async def start(dut, rom, ram):
    """Start the clock, reset the design, then attach the SPI memory model."""
    clock = Clock(dut.clk, 10, unit="us")  # 100 kHz
    cocotb.start_soon(clock.start())

    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 10)
    dut.rst_n.value = 1

    cocotb.start_soon(spi_mem(dut, rom, ram))


@cocotb.test()
async def test_add(dut):
    """add.asm: RAM[0] = 2 + 3, then spin in a halt loop."""
    rom = load_hack("add.hack")
    ram = {}
    await start(dut, rom, ram)

    # 6 instructions to the store; ~100 clks per fetch plus ~100 per PSRAM access
    await ClockCycles(dut.clk, 3000)

    dut._log.info(f"RAM after run: {ram}")
    assert ram.get(0) == 5, f"expected RAM[0] == 5, got {ram.get(0)}"


async def run_until_done(dut, ram, max_clocks):
    """Poll for the program's done marker (see hack_ops.py) instead of
    guessing a fixed run length."""
    for elapsed in range(0, max_clocks, 200):
        if ram.get(hack_ops.DONE_ADDR) == hack_ops.DONE_VALUE:
            dut._log.info(f"program done after ~{elapsed} clocks")
            return
        await ClockCycles(dut.clk, 200)
    assert False, f"program did not finish within {max_clocks} clocks"


async def run_ops_program(dut, name, max_clocks=200_000):
    """Run programs/<name>.hack and check RAM against hack_ops' expectations.
    Reports every mismatch, not just the first."""
    rom = load_hack(f"{name}.hack")
    ram = {}
    await start(dut, rom, ram)
    await run_until_done(dut, ram, max_clocks)

    expected = hack_ops.PROGRAMS[name][1]()
    errors = []
    for addr, want in sorted(expected.items()):
        got = ram.get(addr)
        if got != want:
            fmt = lambda v: "unwritten" if v is None else f"{v:#06x}"
            errors.append(f"RAM[{addr}]: expected {fmt(want)}, got {fmt(got)}")
    for e in errors:
        dut._log.error(e)
    assert not errors, f"{len(errors)} mismatches in {name}"
    dut._log.info(f"{name}: all {len(expected)} checks passed")


@cocotb.test()
async def test_alu_ops(dut):
    """All 28 comp mnemonics (A and M forms) on two operand pairs."""
    await run_ops_program(dut, "alu_ops")


@cocotb.test()
async def test_dest_ops(dut):
    """All 8 dest combinations, M written to the old A, plus read-modify-write."""
    await run_ops_program(dut, "dest_ops")


@cocotb.test()
async def test_jump_ops(dut):
    """All 8 jump conditions against negative, zero and positive values."""
    await run_ops_program(dut, "jump_ops")
