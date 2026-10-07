# The NVMe SSD on the PCIe HAT drops off the bus when the drive or the link
# goes into a power-saving state ("controller is down; will reset:
# CSTS=0xffffffff"). Keep both awake. The kernel suggests exactly this set.
CMDLINE:append = " nvme_core.default_ps_max_latency_us=0 pcie_aspm=off pcie_port_pm=off"
