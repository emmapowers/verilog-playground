import glob
import logging
import os
from pathlib import Path

from cocotb_tools.runner import get_runner
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from bitstring import BitArray
from .coco_helper import coco_test


@coco_test("bcd_to_seven_segment", params={"Digits": 10})
async def test_valid_inputs(dut):
    """Test valid BCD inputs from 0 to 9."""

    # Valid BCD digits are 0-9
    dut.bcd.value = BitArray(
        ",".join(f"uint4={n}" for n in reversed([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]))
    ).int
    await Timer(10, unit="ns")
    assert dut.segments.value[0] == 0b0111111
    assert dut.segments.value[1] == 0b0000110
    assert dut.segments.value[2] == 0b1011011
    assert dut.segments.value[3] == 0b1001111
    assert dut.segments.value[4] == 0b1100110
    assert dut.segments.value[5] == 0b1101101
    assert dut.segments.value[6] == 0b1111101
    assert dut.segments.value[7] == 0b0000111
    assert dut.segments.value[8] == 0b1111111
    assert dut.segments.value[9] == 0b1101111


@coco_test("bcd_to_seven_segment", params={"Digits": 6})
async def test_invalid_inputs(dut):
    """Test invalid BCD inputs from 10 to 15."""

    # Invalid BCD digits are 10-15
    dut.bcd.value = BitArray(
        ",".join(f"uint4={n}" for n in reversed([0, 11, 12, 13, 14, 15]))
    ).int
    await Timer(10, unit="ns")
    assert dut.segments.value[0] == 0b0111111
    assert dut.segments.value[1] == 0b0000000
    assert dut.segments.value[2] == 0b0000000
    assert dut.segments.value[3] == 0b0000000
    assert dut.segments.value[4] == 0b0000000
    assert dut.segments.value[5] == 0b000000


@coco_test("bcd_to_seven_segment", params={"Digits": 1})
async def test_change_inputs(dut):
    """Test changing BCD inputs."""

    dut.bcd.value = 0
    await Timer(10, unit="ns")
    assert dut.segments.value == [0b0111111]

    dut.bcd.value = 1
    await Timer(10, unit="ns")
    assert dut.segments.value == [0b0000110]
