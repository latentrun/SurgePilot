# 03. Domain Model Overview

TODO: Write down the core domain model, entity relationships, status and life cycle.

## Pending Slice Model References

Before this article completes the complete domain model, the Run / Run-Node allocation / NodeLease / control request data model of P1 Resource Multi-node is subject to `docs/sdd/slices/P1-01-resource-multi-node.md` §10. When implementing or reviewing the table structure related to multi-node resources, you should first refer to the data model constraints of the Slice to avoid binding `runs.selected_node_id` as the only resource for P1 multi-node execution.
