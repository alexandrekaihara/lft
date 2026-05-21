from onos_topologies.iperf_experiment.diamond_topology.main import main

# OSPF
for i in range(1, 11):
    main(
        algorithm="5",
        hindering="degrade",
        auto_start=False,
        run_name=f"ospf-degrade-{i:02d}",
    )

# CDN-QoE
for i in range(1, 11):
    main(
        algorithm="1",
        hindering="degrade",
        auto_start=True,
        run_name=f"cdn-qoe-degrade-{i:02d}",
    )

# FWD
for i in range(1, 11):
    main(
        algorithm="4",
        hindering="degrade",
        auto_start=False,
        run_name=f"fwd-degrade-{i:02d}",
    )
