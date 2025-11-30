import glob
import logging
import os
from pathlib import Path

from cocotb_tools.runner import get_runner
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer, ClockCycles
import cocotb
from .coco_helper import coco_test


@coco_test("baud_gen", build_kwargs={"build_args": ["-Wno-fatal"]})
async def test_115200_baud(dut):
    """Test a single digit decimal input to bcd"""

    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    dut.baud_rate.value = 115200
    dut.rst.value = 1

    await RisingEdge(dut.clk)
    dut.rst.value = 0

    await ClockCycles(dut.clk, 866, rising=True)
    assert dut.baud_en.value == 0
    await RisingEdge(dut.clk)
    assert dut.baud_en.value == 1
    await RisingEdge(dut.clk)
    #assert dut.baud_en.value == 0
    await ClockCycles(dut.clk, 32, rising=True)


