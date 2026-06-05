#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore")

import os
import sys
import shlex
import subprocess
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent

RUNNABLE = {
    "diamond_topology": "onos_topologies.iperf_experiment.diamond_topology.main",
    "rnp_topology": "onos_topologies.iperf_experiment.rnp_topology.main",
}
EXCLUDE       = {"__init__", "constants", "dependencies"}
TRAFFIC_TYPES = ("ping", "iperf", "ffmpeg")


# helpers

def docker_cleanup():
    ids = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True).stdout.strip()
    if ids:
        containers = ids.splitlines()
        subprocess.run(["docker", "rm", "-f"] + containers)
        click.echo(f"*** removed {len(containers)} container(s)")
    else:
        click.echo("*** no containers running")


def discover_experiments():
    found = {}
    exp_dir = ROOT / "experiment"
    if exp_dir.is_dir():
        for f in sorted(exp_dir.glob("*.py")):
            if f.stem not in EXCLUDE:
                found[f.stem] = f.relative_to(ROOT)
    for name, module in RUNNABLE.items():
        found[name] = (ROOT / Path(*module.split(".")).with_suffix(".py")).relative_to(ROOT)
    return found


# topology helpers

def _load_config(path: Path) -> dict:
    import importlib.util
    spec = importlib.util.spec_from_file_location("_cfg", path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("CONFIG", "DEFAULT_CONFIG", "DEBUG_CONFIG"):
        cfg = getattr(mod, name, None)
        if isinstance(cfg, dict) and "pops" in cfg:
            return cfg
    raise SystemExit(f"no valid config found in {path} - expected CONFIG, DEFAULT_CONFIG or DEBUG_CONFIG")


# topology repl

REPL_HELP = """\
commands:
  create host <name> <ip>      add a host
  create switch <name>         add a switch
  connect <name1> <name2>      link two nodes
  traffic <ping|iperf> <n1> <n2>
  ls [hosts|switches]
  quit / help"""


def _run_repl(topo):
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break
        if not line:
            continue
        if line in ("quit", "exit"):
            docker_cleanup()
            break
        if line in ("help", "?"):
            click.echo(REPL_HELP)
            continue
        try:
            cmd, *rest = shlex.split(line)
        except ValueError as e:
            click.echo(f"parse error: {e}")
            continue

        if cmd == "create":
            if rest[:1] == ["switch"] and len(rest) == 2:
                topo.create_switch(rest[1])
            elif rest[:1] == ["host"] and len(rest) == 3:
                name, ip = rest[1], rest[2]
                if name in topo._host_ips:
                    click.echo(f"error: host '{name}' already exists")
                elif ip in topo._host_ips.values():
                    click.echo(f"error: IP {ip} already in use")
                else:
                    topo.create_host(name, ip)
            else:
                click.echo("usage: create switch <name>  |  create host <name> <ip>")

        elif cmd == "connect" and len(rest) == 2:
            try:
                topo.connect_nodes(rest[0], rest[1])
            except ValueError as e:
                click.echo(f"error: {e}")

        elif cmd == "traffic" and len(rest) == 3:
            ttype, n1, n2 = rest
            ip2 = topo._host_ips.get(n2)
            if not ip2:
                click.echo(f"unknown host: {n2}")
                continue
            if ttype == "iperf":
                click.echo(f"*** iperf {n1} -> {n2} ({ip2})")
                node2 = topo.clients.get(n2) or topo.servers.get(n2)
                node2.startServer(port=5201)
                subprocess.run(["docker", "exec", n1, "iperf3", "-c", ip2, "-p", "5201", "-t", "10"])
            elif ttype == "ping":
                subprocess.run(["docker", "exec", n1, "ping", "-c", "4", ip2])
            else:
                click.echo(f"unknown traffic type: {ttype}")

        elif cmd == "ls":
            kind = rest[0] if rest else "all"
            if kind in ("all", "host", "hosts"):
                for name, ip in getattr(topo, "_host_ips", {}).items():
                    click.echo(f"  host    {name}  {ip}")
            if kind in ("all", "switch", "switches"):
                for name in topo.switches:
                    click.echo(f"  switch  {name}")

        else:
            click.echo(f"unknown command: {cmd}  (type 'help')")


# cli

@click.group()
def cli():
    """LFT - Network Emulation Tool"""
    if os.geteuid() != 0:
        raise SystemExit("*** lft must be run as root: sudo lft ...")


@cli.command()
@click.argument("name", required=False)
def experiment(name):
    """List or run available experiments"""
    experiments = discover_experiments()
    if name is None:
        width = max((len(n) for n in experiments), default=4)
        for n, path in experiments.items():
            click.echo(f"  {n:<{width}}  {path}")
        return
    if name not in experiments:
        raise SystemExit(f"experiment not found: {name}")
    docker_cleanup()
    script = ROOT / experiments[name]
    result = subprocess.run(["python3", str(script)], cwd=script.parent)
    docker_cleanup()
    sys.exit(result.returncode)


@cli.group()
def topology():
    """Create a network topology"""


@topology.command("create")
@click.option("--manual", is_flag=True, help="Open interactive REPL (empty topology)")
@click.option("--path", type=click.Path(exists=True), help="Load config from a constants.py and run")
def topology_create(manual, path):
    """Start ONOS and build a topology interactively or from a config file"""
    sys.path.insert(0, str(ROOT))
    from onos_topologies.dash_topology.dash_topology import DashTopology

    if manual:
        docker_cleanup()
        topo = DashTopology(config={
            "pops": (), "adjacency_matrix": (),
            "apply_link_properties": False, "randomize_link_properties": False,
            "throughput": "300mbit", "delay": "10ms", "jitter": "5ms",
        })
        print("*** Starting ONOS controller (waiting ~30s)...", flush=True)
        topo.start_controller()
        print(f"*** ONOS ready - IP: {topo.onos_ip}", flush=True)
        _run_repl(topo)
    elif path:
        docker_cleanup()
        config = _load_config(Path(path))
        topo = DashTopology(config=config)
        topo.run(run_discovery=True, disable_fwd=False)
        _run_repl(topo)
    else:
        raise SystemExit("use --manual for interactive mode or --path <constants.py>")


@cli.group()
def utils():
    """Utility commands"""


@utils.command("clean")
def utils_clean():
    """Remove all running Docker containers"""
    docker_cleanup()


main = cli

if __name__ == "__main__":
    cli()
