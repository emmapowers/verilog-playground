"""Constants and enums for vproj."""

from __future__ import annotations

from enum import StrEnum, auto


class Fileset(StrEnum):
    """Vivado fileset identifiers."""

    SOURCES = "sources_1"
    CONSTRAINTS = "constrs_1"
    SIMULATION = "sim_1"


class RunName(StrEnum):
    """Vivado run identifiers."""

    SYNTH = "synth_1"
    IMPL = "impl_1"


class FileKind(StrEnum):
    """File type categories."""

    HDL = auto()
    HEADER = auto()
    IP = auto()
    XDC = auto()
    SIM = auto()
    OTHER = auto()


# Mapping from file kind to fileset
KIND_TO_FILESET: dict[FileKind, Fileset] = {
    FileKind.HDL: Fileset.SOURCES,
    FileKind.HEADER: Fileset.SOURCES,
    FileKind.IP: Fileset.SOURCES,
    FileKind.XDC: Fileset.CONSTRAINTS,
    FileKind.SIM: Fileset.SIMULATION,
    FileKind.OTHER: Fileset.SOURCES,
}
