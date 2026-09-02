# ADR-0004: Execute on One Manually Selected Node

- Status: Accepted

Each initial Run binds to exactly one user-selected Idle Load Node. This makes selection explicit and keeps lease acquisition, snapshot attribution, Stop, failure cleanup, and report ownership deterministic. Automatic allocation, queuing, and multi-node execution would require scheduling policy, aggregate reporting, partial-failure semantics, and multi-resource lease behavior, so they remain outside the initial milestone.
