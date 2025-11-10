import glob
import logging
import os
from pathlib import Path

from cocotb_tools.runner import get_runner
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
import cocotb
from .coco_helper import coco_test


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_single_digit(dut):
    """Test a single digit decimal input to bcd"""

    dut.decimal.value = 3
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 3


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_two_digits(dut):
    """Test a two digit decimal input to bcd"""

    dut.decimal.value = 12
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0001_0010


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_three_digits(dut):
    """Test three digit decimal input to bcd"""

    dut.decimal.value = 123
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0001_0010_0011


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_max_decimal(dut):
    """Test max decimal input to bcd, output is truncated to fit MaxDigits"""

    dut.decimal.value = 0b1111111111  # 1023 decimal
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0000_0010_0011  # 023 BCD


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_zero_decimal(dut):
    """Test zero decimal input to bcd"""

    dut.decimal.value = 0
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0


@coco_test("bcd_encoder", params={"DecimalWidth": 10, "MaxDigits": 3})
async def test_changing_input(dut):
    """Test changing decimal input to bcd"""

    dut.decimal.value = 3
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 3

    dut.decimal.value = 5
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 5

    dut.decimal.value = 12
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0001_0010  # 12 BCD

    dut.decimal.value = 431
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0100_0011_0001  # 431 BCD

    dut.decimal.value = 777
    await Timer(10, unit="ns")
    logging.error(f"BCD Output: {dut.bcd.value}")
    assert dut.bcd.value == 0b0111_0111_0111  # 777 BCD
