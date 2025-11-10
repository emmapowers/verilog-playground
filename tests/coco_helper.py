from functools import wraps
import hashlib
import os, re, glob
from pathlib import Path

from cocotb_tools.runner import get_runner
import cocotb


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


proj_path = (Path(__file__).parent / ".." / "fpga.srcs" / "sources_1" / "new").resolve()


def project_sources():
    files = [
        file
        for file in glob.glob(str(proj_path / "*.sv"))
        if not os.path.basename(file).startswith(
            "tb_"
        )  # skip if the file name starts with "tb_", but we have to handle the full path
    ]
    return [*files, *glob.glob(str(proj_path / "*.svh"))]


def _stable_hash(obj) -> str:
    """
    Deterministic hash() replacement.
    Returns the first 8 hex characters of the SHA-1 digest of `obj`.
    """
    data = repr(obj).encode("utf-8")
    return hashlib.sha1(data).hexdigest()[:8]


def _run(
    top: str,
    testcase_fn: callable,
    *,
    params: dict[str, int] | None = None,
    timescale: tuple[str, str] = ("1ns", "1ps"),
    build_kwargs: dict | None = None,
    run_kwargs: dict | None = None,
):
    testcase_module = testcase_fn.__module__
    testcase_name = testcase_fn.__name__  # use the pytest test name
    build_dir = (
        (Path(__file__).parent / ".build").resolve()
        / ".build"
        / _stable_hash(
            (
                top,
                frozenset(params.items()),
                frozenset(build_kwargs.items()) if build_kwargs else (),
            )
        ).__str__()
    )
    test_dir = (Path(__file__).parent / ".output" / _slug(testcase_name)).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    runner = get_runner("verilator")

    runner.build(
        sources=project_sources(),
        hdl_toplevel=top,
        parameters=params or {},
        includes=[proj_path],
        build_dir=str(build_dir),
        timescale=timescale,
        waves=True,
        **build_kwargs or {},
    )

    newEnv = os.environ.copy()
    newEnv["COCOTB_SIM"] = "1"
    runner.test(
        hdl_toplevel=top,
        test_module=testcase_module,
        testcase=testcase_name,
        test_dir=str(test_dir),
        timescale=timescale,
        waves=True,
        extra_env=newEnv,
        **run_kwargs or {},
    )

    # find a waveform (VCD/FST) created by this run
    for pattern in ("*.fst", "*.vcd", "sim_build/*.fst", "sim_build/*.vcd"):
        found = glob.glob(str(test_dir / pattern))
        if found:
            return Path(found[0]).resolve()
    return test_dir


def coco_test(
    top: str,
    *,
    params: dict[str, int] | None = None,
    timescale: tuple[str, str] = ("1ns", "1ps"),
    build_kwargs: dict | None = None,
    run_kwargs: dict | None = None,
):
    def _decorator(fn: callable):
        if os.getenv("COCOTB_SIM"):
            return cocotb.test()(fn)

        @wraps(fn)
        def _wrapper(*args, **kwargs):
            _run(
                top,
                fn,
                params=params,
                timescale=timescale,
                build_kwargs=build_kwargs,
                run_kwargs=run_kwargs,
            )
            return None

        return _wrapper

    return _decorator
