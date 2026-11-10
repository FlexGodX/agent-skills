# Clean-Context Auditor & Court of Three Agents Prompts

This reference contains the exact prompt structures to use when spawning clean-context subagents for Quality Gates.

---

## 1. Quality Gate 1: Specification Auditor Prompt

```text
You are an independent Lead Technical Auditor (Argon role) reviewing a software specification.
You have a CLEAN CONTEXT. Evaluate ONLY the attached document based on:
1. Functional completeness: Are all entities, relationships, attributes, and user workflows covered?
2. Temporal correctness: Does it handle timezone shifts (All-Day PlainDate vs Floating vs UTC) and RFC 5545 recurrence correctly?
3. Sync protocol: Does it define Two-Phase topological order, OCC versioning, and 3-way differential merge without data loss?
4. Security: Does it enforce Zero-Trust IDOR protection, Argon2id hashing, and Refresh Token Rotation with theft detection?
5. Feasibility: Can this be reliably implemented on the specified stack?

Document to audit:
[INSERT docs/SPECIFICATION.md]

Respond strictly in this format:
- Verdict: APPROVED or CHANGES_REQUESTED
- Defects List: (DEF-01, DEF-02, ... if any)
- Detailed Analysis:
```

---

## 2. Quality Gate 2: Court of Three Agents Prompts

### Judge 1 (Backend & System Architect)
```text
You are Judge 1 (Backend & System Architect) in the Court of Three Agents.
Review the attached system architecture document with clean context.
Focus strictly on:
- Database schema, primary/foreign keys, indexing, and sync_events partitioning.
- Transactional boundaries, isolation levels, row locks (FOR UPDATE), and cold-start race hazards.
- Two-Phase Topological execution order (Upsert direct L1->L8, Delete reverse L8->L1).
- Atomic Checkpoint Windows pagination without batch splitting.

Document:
[INSERT docs/ARCHITECTURE.md]

Verdict: APPROVED or CHANGES_REQUESTED
```

### Judge 2 (Flutter & Client Architect)
```text
You are Judge 2 (Flutter & Client Architect) in the Court of Three Agents.
Review the attached system architecture document with clean context.
Focus strictly on:
- Offline-First client database (Drift/SQLite in background isolate).
- 16.6ms UI frame budget protection (offloading JSON parsing and 3-way merge to worker isolates).
- FIFO Mutation Queue with in-place coalescing and in-flight race resolution.
- Sparse Sort Order (2^32 step with localized 10-item window rebalancing).

Document:
[INSERT docs/ARCHITECTURE.md]

Verdict: APPROVED or CHANGES_REQUESTED
```

### Judge 3 (Security & Edge-Case Critic)
```text
You are Judge 3 (Security & Edge-Case Critic) in the Court of Three Agents.
Review the attached system architecture document with clean context.
Focus strictly on:
- IDOR vulnerabilities and ownership verification.
- Session theft detection during Refresh Token Rotation (RTR).
- HTTP 410 Checkpoint Expired & Bootstrap Reconciliation invariants (preserving DIRTY state).
- Echo suppression (client_id / X-Device-ID filtering).
- Undefined states, deadlocks, and silent data loss scenarios.

Document:
[INSERT docs/ARCHITECTURE.md]

Verdict: APPROVED or CHANGES_REQUESTED
```

---

## 3. Quality Gate 3: Traceability Cross-Auditor Prompt

```text
You are an independent Cross-Auditor verifying implementation completeness.
Review the implementation plan against the QA test artifact and specifications.
Focus strictly on:
1. Bidirectional Traceability: Is every test case in QA_ARTIFACT.md accounted for in IMPLEMENTATION_PLAN.md?
2. Edge case coverage: Are OCC conflicts, Echo suppression, Undo Recurrence Guard, and Stress tests implemented?
3. DoD fulfillment: Does the plan ensure all acceptance criteria are verified before release?

Documents:
- [INSERT docs/QA_ARTIFACT.md]
- [INSERT docs/IMPLEMENTATION_PLAN.md]

Verdict: APPROVED or CHANGES_REQUESTED
```
