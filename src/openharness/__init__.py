"""Compatibility package for the former ``openharness`` import path.

AgentChart is the new package name.  This shim keeps older imports working while
downstream code migrates to ``agentchart``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys

_PREFIX = "openharness."
_TARGET_PREFIX = "agentchart."


class _OpenHarnessAliasFinder(importlib.abc.MetaPathFinder):
    """Map old ``openharness.*`` imports onto ``agentchart.*`` modules."""

    def find_spec(
        self,
        fullname: str,
        path: object | None = None,
        target: object | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        if not fullname.startswith(_PREFIX):
            return None
        if fullname in {"openharness.__main__", "openharness.cli"}:
            return None
        target_name = _TARGET_PREFIX + fullname[len(_PREFIX) :]
        spec = importlib.util.find_spec(target_name)
        if spec is None:
            return None
        return importlib.machinery.ModuleSpec(
            fullname,
            _OpenHarnessAliasLoader(fullname, target_name),
            is_package=spec.submodule_search_locations is not None,
        )


class _OpenHarnessAliasLoader(importlib.abc.Loader):
    def __init__(self, alias_name: str, target_name: str) -> None:
        self.alias_name = alias_name
        self.target_name = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> object:
        module = importlib.import_module(self.target_name)
        sys.modules[self.alias_name] = module
        return module

    def exec_module(self, module: object) -> None:
        return None


if not any(isinstance(finder, _OpenHarnessAliasFinder) for finder in sys.meta_path):
    sys.meta_path.insert(0, _OpenHarnessAliasFinder())

_agentchart = importlib.import_module("agentchart")

for key, value in _agentchart.__dict__.items():
    if key in {"__name__", "__package__", "__loader__", "__spec__"}:
        continue
    globals()[key] = value
