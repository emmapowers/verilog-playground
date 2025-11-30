from functools import wraps, cache
import hashlib
import os, re, glob
from pathlib import Path

from cocotb_tools.runner import get_runner
import cocotb


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)


_proj_root = (Path(__file__).parent / "..").resolve()


@cache
def _get_vproj_sources() -> tuple[list[str], list[Path]]:
    """Get source files and include dirs from vproj (requires Vivado server)."""
    from vproj.project import list_cmd

    files_info = list_cmd(
        proj_hint=_proj_root, proj_dir=None, settings=None,
        quiet=True, daemon=True, return_data=True
    )

    if not files_info:
        raise RuntimeError(
            "Could not get project files. Is Vivado server running? "
            "Try: vproj server start"
        )

    hdl_types = {"SystemVerilog", "Verilog", "Verilog Header"}
    sources = []
    include_dirs: set[Path] = set()

    for fileset, path, ftype in files_info:
        if ftype not in hdl_types or fileset != "sources_1":
            continue
        full_path = (_proj_root / path).resolve()
        sources.append(str(full_path))
        # Add parent dir of headers as include path
        if ftype == "Verilog Header":
            include_dirs.add(full_path.parent)
        else:
            # Also add source dirs for `include directives
            include_dirs.add(full_path.parent)

    return sources, list(include_dirs)


def project_sources() -> list[str]:
    sources, _ = _get_vproj_sources()
    return sources


def project_includes() -> list[Path]:
    _, includes = _get_vproj_sources()
    return includes


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
        / _stable_hash((top, params, build_kwargs))
    )
    test_dir = (Path(__file__).parent / ".output" / _slug(testcase_name)).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    test_dir.mkdir(parents=True, exist_ok=True)

    runner = get_runner("verilator")

    runner.build(
        sources=project_sources(),
        hdl_toplevel=top,
        parameters=params or {},
        includes=project_includes(),
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
