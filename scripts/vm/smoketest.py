"""LFT lab smoketest: build the diamond topology and run one experiment.

This is the exact validation script used on the production lft-vm (tupana)
when the KVM migration was validated. It targets the legacy
``iperf_experiment`` layout kept for reference; on the current reorganized
tree use the CLI (``python cli.py``) or ``onos_topologies/create_n_run.py``.

Usage (inside the VM, from the repo root):
    python3 scripts/vm/smoketest.py
"""
import os
import sys

LFT_HOME = os.environ.get("LFT_HOME", os.getcwd())
sys.path.insert(0, os.path.join(LFT_HOME, "onos_topologies/iperf_experiment/diamond_topology"))
sys.path.insert(0, LFT_HOME)

from main import main  # noqa: E402

main(algorithm="4", hindering="degrade", auto_start=True, run_name="smoketest")
