.. _simulated-baremetal:

===========================================
Simulated Baremetal Environment for Testing
===========================================

Its not always feasible to provide a real hardware environment for testing
baremetal deployment. So to accommodate testing baremetal deployment in CI, we
create a simulated baremetal environment using virtual machines and virtual
switches, which can be used in place of real servers and real switches.

There are a couple of different virtual switching technologies which we support
for the simulated environment, linuxbridge and openvswitch, which of these you
pick does not affect the technology you choose for your neutron deployment.

Example Simulation Topology in an OpenStack environment
=========================================================

::

 External/Control plane networks
 +---------------------------------------------------------------+----------------+-----------------------------+
                                                                 |                |
                                                                 |                |
                                                             +---+----+       +---+----+
 +-----------------------------------------------------------+        +-------+        +------------------------+
 |Controller Node                                            |  eth1  |       |  eth0  |                        |
 |   +---------------------------------------------------+   |        |       |        |                        |
 |   |BareMetal Simulation                               |   +---+----+       +----+---+                        |
 |   | +-----+    +-----+      +-----+      +-----+      |       |                 |       +----------------+   |
 |   | | BVM |    | BVM |      | BVM |      | BVM |      |       |                 |       |                |   |
 |   | |     |    |     |      |     |      |     |      |       |                 +-------+      Nova      |   |
 |   | +--+--+    +--+--+      +--+--+      +--+--+      |       |                 |       |                |   |
 |   |    |          |            |            |         |       |                 |       +----------------+   |
 |   |    |          |            |            |         |       |                 |                            |
 |   |    |          |            |            |         |       |                 |       +----------------+   |
 |   |    |          |            |            |         |       |                 |       |                |   |
 |   |    |          |            |            |         |       |                 +-------+     Ironic     |   |
 |   |  +-+----------+------------+------------+---+     |       |                 |       |                |   |
 |   |  |                                          |     |       |                 |       +----------------+   |
 |   |  |                                          |     |       |                 |                            |
 |   |  |                 OVS/LB                   |     |       |                 |       +----------------+   |
 |   |  |                                          |     |       |                 |       |                |   |
 |   |  |        +-------------+                   |     |       |                 +-------+     Neutron    |   |
 |   |  +--------+             +-------------------+     |       |                         |                |   |
 |   |           |             |                         |       |                         +----------------+   |
 |   |           | bmintswitch |                         |       |                                              |
 |   +-----------+             +-------------------------+       |                                              |
 |               |             |                                 |                                              |
 |               +------+------+                                 |                                              |
 |                      |                                        |                                              |
 |                      |                                        |                                              |
 |               +------+------+                                 |                                              |
 |               |             |                                 |                                              |
 |   +-----------+  bminthost  +---------------------------------+----+                                         |
 |   |           |             |                                      |                                         |
 |   |           +-------------+     Neutron OVS/LB                   |                                         |
 |   |                                                                |                                         |
 |   +----------------------------------------------------------------+                                         |
 |                                                                                                              |
 +--------------------------------------------------------------------------------------------------------------+
