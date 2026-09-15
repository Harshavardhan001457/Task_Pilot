# FlowStar NS-3 Implementation vs. Research Paper: Comprehensive Comparison Report

**Reference Paper:**  
*FlowStar: Fast Convergence Per-Flow State Accurate Congestion Control for InfiniBand*  
Authors: Changyun Luo, Huaxi Gu, Lijing Zhu, Huixia Zhang  
Published in: *IEEE/ACM Transactions on Networking*, Vol. 32, No. 3, June 2024 (pp. 2662–2674)  
Digital Object Identifier: `10.1109/TNET.2024.3363658`

**Evaluated Project:** `FlowStar-NS3` (ns-3.48 simulation prototype)  
**Date of Audit:** September 15, 2026  

---

## 1. Executive Summary & Audit Verdict

This report presents a thorough, mechanism-by-mechanism architectural audit and functional verification of the `FlowStar-NS3` codebase against the published IEEE/ACM ToN 2024 research paper. It also analyzes the four custom improvements introduced into the repository.

### High-Level Verdict

The project represents a substantial, compiling, and passing C++ simulation framework in ns-3.48 that captures the high-level philosophy of FlowStar (per-flow queueing, BECN/CNP control signaling, and multi-stage rate adaptation). However, **the codebase diverges significantly from the paper's actual algorithms, protocol mechanics, and experimental setup**, and suffers from several **architectural simplifications, missing features, and evaluation pipeline flaws**:

1. **Algorithm 1 (Dynamic Queue Assignment) Divergences:** The paper's DQA tracks active message counts in a Queue Table (`QT`) and dynamically deletes entries from the Message Table (`MT`) upon dequeuing the final packet of a message (`seq == Message.length`). The ns-3 implementation lacks packet sequence numbers or message length fields in its tag, cannot detect message completion, and **never deletes entries from `MT` at runtime**, causing queues to remain permanently assigned.
2. **Credit-Based Flow Control (CBFC) Simplification:** In the paper, CBFC is an InfiniBand link-layer, hop-by-hop credit mechanism between adjacent switches tracking `ABR`, `FCCL`, and `FCTBS`. In the project, CBFC is implemented as an **end-to-end receiver-to-sender credit return path** via `CreditUpdateHeader` packets, bypassing switch-level hop-by-hop backpressure. Furthermore, in the final evaluation script (`phase5-evaluation.cc`), credit managers were not wired to senders, rendering credit gating dormant.
3. **Congestion Differentiation & ECN Missing in Switch:** The paper differentiates congestion by inspecting whether the next hop of the switch port connects to a switch (Fabric congestion) or a host (Endpoint congestion). In the project, `FlowStarSwitchAgent` sends BECNs for all congestion without inspecting hop types, and `CbfcQueueDisc` **never marks forward packets with ECN**. The receiver must rely on an ad-hoc local rate-drop heuristic to trigger CNPs.
4. **Algorithm 2 (Rate Regulation) Contradictions:**
   - **Rate Decrease on BECN:** The paper explicitly mandates that fabric congestion (BECN) **must not reduce sending rates**, but instead triggers multipath load balancing. The codebase's `FlowStarRateController::OnBecn` does a **multiplicative decrease (cuts rate by 50%)**, directly contradicting the paper.
   - **Rate Recovery Formula:** The paper uses an exact exponential smoothing formula $currRate = lineRate \times \alpha + currRate \times (1 - \alpha)$ with $\alpha$ doubling each period ($1/64 \to 1$). The codebase replaces this with an ad-hoc AIMD / piecewise linear-proportional state machine (`SLOW_RECOVERY` adding 100 Mbps, then `AGGRESSIVE_RECOVERY`).
5. **Improvement Efficacy:**
   - **Improvement 1 (DQA Scoring):** Inactive during simulations because `SetQueueCongestionSignals` is never invoked at runtime; scores collapse to raw queue occupancy, behaving identically to baseline DQA.
   - **Improvement 2 (Hybrid State):** `RemoveFlow()` is never invoked at runtime. In the final benchmark, Modes F1 and F2 produce 100% identical outputs across all seeds.
   - **Improvement 3 (Adaptive Routing):** Unit-tested and functional at the socket level, but omitted from the final benchmark runner.
   - **Improvement 4 (Severity Recovery):** Implemented on top of the non-paper AIMD controller and excluded from the final evaluation matrix.
6. **Evaluation Pipeline Defect:** The evaluation script computes `throughput_bps = rx * 1000 * 8` (total bits received across the whole run, without dividing by duration or time). Comparing F0 (3 senders, 10,000 packets) against F1/F2 (2 senders, 2,000 packets) created an artificial appearance of a 2.14 Gbps vs. 96 Mbps throughput difference.

---

## 2. Feature-by-Feature Compliance Scorecard

| Category | Paper Specification | Repository Implementation | Status in Codebase | Working as Expected? |
| :--- | :--- | :--- | :---: | :---: |
| **Flow Identifier (MID)** | 4-tuple: `(SrcLid, DstLid, SrcQPN, DstQPN)` | `FlowStarMid`: `(srcNodeId, dstNodeId, srcFlowId, dstFlowId)` tagged via `FlowStarMidTag` | **Implemented** | **Yes** (Accurate simulation abstraction of IB LID/QP) |
| **DQA: Empty Queue Selection** | Random selection from available empty queues (`emptyQ.random`) | First unoccupied queue found via linear scan in `AssignQueue` | **Partial** | **Substantially** (Deterministic first-fit rather than uniform random) |
| **DQA: Queue Sharing Fallback** | Choose queue with minimum message count (`QT.min`) | Choose queue with least packet occupancy (`leastOccupancy`) | **Divergent** | **Partial** (Considers packet buffer depth instead of message count) |
| **DQA: Flow De-allocation** | On packet `seq == Message.length`, decrement `QT`, delete entry from `MT` upon dequeue | `RemoveFlow()` method exists in `CbfcQueueDisc`, but is **never called** upon packet dequeue or flow end | **Broken / Missing** | **No** (Queues remain permanently occupied; no dynamic reuse in simulation) |
| **Hop-by-Hop CBFC** | Hop-by-hop link layer between switches/hosts: downstream sends `FCCL = ABR + BufferFree` to upstream | Replaced by **end-to-end receiver-to-sender** UDP `CreditUpdateHeader` control packets | **Architectural Divergence** | **No** (Does not model link-layer hop-by-hop backpressure; dormant in Phase 5) |
| **Switch Scheduler** | Round-Robin (RR), FCFS, and Strict Priority (FQ for short messages via RETH DMAlen, SQ for long) | Round-Robin across non-empty internal queues in `CbfcQueueDisc::DoDequeue` | **Partial** | **RR Works**; Strict Priority with DMAlen is **Missing** |
| **Congestion Differentiation** | Check switch next hop: next hop is switch $\to$ Fabric congestion; next hop is host $\to$ Endpoint congestion | No next-hop check. `FlowStarSwitchAgent` sends BECN whenever internal queue occupancy exceeds threshold | **Missing** | **No** (Cannot differentiate fabric from endpoint congestion) |
| **Endpoint ECN Marking** | Switch marks forward packet with ECN when last-hop queue is congested | `CbfcQueueDisc` does **not** mark forward packets with ECN. Code checks `EcnTag`, but it is never added by switch | **Missing** | **No** (ECN forward marking never triggers in FlowStar switch) |
| **Endpoint CNP Generation** | Receiver receives ECN-marked packet $\to$ sends CNP carrying measured `recvRate` in 24-bit PSN field | Receiver uses tumbling window rate. Because ECN is absent, falls back to custom heuristic: `currentRate < 0.8 * expectedRate` | **Divergent** | **Functionally generates CNP**, but via rate-drop heuristic rather than ECN trigger |
| **Endpoint Rate Decrease** | Sender receives CNP $\to$ `currRate = recvRate`, `CFlag = 1`, `alpha = 1/64` | `FlowStarRateController::OnCnp`: sets `currentRate = recvRate * factor`, sets state to `SLOW_RECOVERY` | **Divergent** | **Partially works**, but does not initialize $\alpha = 1/64$ or set `CFlag` |
| **Rate Recovery Formula** | Algorithm 2: $currRate = lineRate \times \alpha + currRate \times (1 - \alpha)$, doubling $\alpha$ every interval $T$ | State machine: `SLOW_RECOVERY` (adds 100 Mbps additive step) $\to$ `AGGRESSIVE_RECOVERY` (proportional step) | **Divergent** | **Works as custom AIMD**, but **does not implement the paper's formula** |
| **Fabric Congestion (BECN)** | Switch sends BECN to source CA; source CA enables multipath load balancing; **rate is NOT decreased** | Switch sends BECN; sender executes **Multiplicative Decrease (rate $\times$ 0.5)** | **Contradicts Paper** | **Opposite of paper specification** |
| **Multipath Load Balancing** | Distribute traffic to alternate paths upon BECN reception | Originally disabled. Added in `FlowStarPathManager` & `FlowStarSender::HandleBecn` | **Implemented** | **Unit-tested OK**, but omitted from evaluation runner |
| **Network Topologies** | Large-scale Dragonfly+ (1088 nodes) and 3-tier Fat-tree (128 nodes) | Point-to-point Dumbbell (2–3 senders, 1 receiver, 2 switches) and 4-switch diamond | **Not Implemented** | **No** (Only toy topologies tested) |
| **HPC Traffic Models** | Mixed MPI (2–64 KB) + I/O (8 MB, 10%), Poisson arrivals across loads $\rho \in [0.1, 1.0]$, real AMG HPC trace | Constant-rate UDP streams of fixed packet counts (e.g. 2,000 or 10,000 packets) | **Not Implemented** | **No** (No load-variation curves, no AMG trace, no MPI mix) |

---

## 3. In-Depth Technical Analysis of Core Mechanisms

### 3.1 Dynamic Queue Assignment (Algorithm 1)

In Section IV-A(1) and Algorithm 1 of the paper, Dynamic Queue Assignment operates as follows:
```text
1: // for each packet entering the port
2: MID = (SrcLid, DstLid, SrcQPN, DstQPN)
3: if Packet.seq == 1 then
4:     if emptyQ.size > 0 then
5:         Qselect <- emptyQ.random
6:     else
7:         Qselect <- QT.min
8:     end if
9:     MT[MID] <- Qselect
10:    QT[Qselect] <- QT[Qselect] + 1
11: else if Packet.seq == Message.length then
12:    Qselect <- MT[MID]
13:    MT[MID].delete
14:    QT[Qselect] <- QT[Qselect] - 1
15: else
16:    Qselect <- MT[MID]
17: end if
```

#### What `FlowStar-NS3` implements:
- `FlowStarMid` represents the 4-tuple, attached to packets using `FlowStarMidTag`.
- In `CbfcQueueDisc::AssignQueue(FlowStarMid mid)`:
  - If `mid` exists in `m_messageTable`, it returns the mapped queue index.
  - If not, it searches `m_queueTable` for an unoccupied queue (`activeMids.empty()`) and takes the first available index.
  - If all queues are occupied, it selects the queue with the lowest packet occupancy (`m_queueTable[i].occupancy`).

#### Defects and Discrepancies:
1. **Lack of Packet Demarcation:** The `FlowStarMidTag` only serializes `(srcNodeId, dstNodeId, srcFlowId, dstFlowId)`. It contains **no packet sequence number (`seq`)** and **no total message length (`Message.length`)**.
2. **Missing Flow De-allocation:** Because the switch cannot identify the final packet of a message, it never triggers lines 11–14 of Algorithm 1. Although a `RemoveFlow(FlowStarMid mid)` method was added to `CbfcQueueDisc`, **it is never called by any network event, application, or socket during simulation**.
3. **Queue Stagnation:** Once physical queues are assigned, they remain bound to their initial MIDs permanently. Subsequent flows arriving after earlier flows have completed are forced into shared queues, even though physical queues are completely idle.
4. **Queue Table Semantics:** The paper's `QT` counts the *number of distinct messages* sharing the queue (`QT[Qselect] + 1`). In the project, line 149 of `cbfc-queue-disc.cc` chooses `leastOccupancy = m_queueTable[i].occupancy`, which is the instantaneous *packet buffer depth*, not the number of assigned messages.

---

### 3.2 Credit-Based Flow Control (CBFC) Mechanism

In Section IV-A(2) and Figure 7 of the paper:
- InfiniBand CBFC operates at the **link layer (hop-by-hop)** between directly connected switches and nodes.
- The downstream switch tracks **Adjusted Blocks Received (`ABR`)** and **`BufferFree`**, periodically transmitting **Flow Control Credit Limit (`FCCL = ABR + BufferFree`)** packets to the upstream switch.
- The upstream switch tracks **Flow Control Total Blocks Sent (`FCTBS`)**, and computes available transmission credits as $Credit = FCCL - FCTBS$. Transmission is strictly halted if $Credit < PacketSize$.

#### What `FlowStar-NS3` implements:
- `model/cbfc-credit-manager.cc` models credit state per MID.
- The code reinterprets the standard terms:
  - `FCTBS` is redefined as "Flow Credit Token Bucket Size" (decreased on send, increased on replenish).
  - `FCCL` is redefined as "Flow Credit Ceiling Level" (token bucket cap).
  - `ABR` is redefined as "Allowed Byte Rate".
- **Hop-by-Hop Link Layer Bypassed:** Switches do **not** send flow control credit packets to upstream switches. Instead, when a packet arrives at the final destination host (`FlowStarReceiver`), the receiver sends a `CreditUpdateHeader` packet back to the sender host.

#### Impact:
- This models an **end-to-end window-based credit loop** across multiple hops rather than link-layer credit backpressure. Hop-by-hop queue buffering and inter-switch pause propagation are not captured by this credit loop.
- In `examples/phase5-evaluation.cc`, line 219: `tx->RegisterCreditManager(cm)` was **omitted entirely**. Consequently, `m_creditManager` is null, and senders run in unthrottled pacing mode without credit gating in Phase 5 evaluations.

---

### 3.3 Congestion Differentiation and Rate Regulation (Algorithm 2)

In Section IV-B and Algorithm 2 of the paper:
```text
Algorithm 2 Rate Regulation
1: // for each receiver QP
2: for each period T do
3:     recvRate <- recvBytes / T
4:     recvBytes <- 0
5: end for
6: if receive packet with congestion notification then
7:     Generate and send CNP with recvRate
8: end if
9: // for each sender QP
10: if receive CNP then
11:    currRate <- recvRate
12:    CFlag <- 1
13:    alpha <- alpha_initial
14: else if not receive CNP during T then
15:    if currRate < lineRate then
16:        if CFlag == 1 then
17:            currRate <- lineRate * alpha + currRate * (1 - alpha)
18:            alpha <- alpha * 2
19:        end if
20:    else
21:        CFlag <- 0
22:    end if
23: end if
24: if receive BECN then
25:    Enable load balancing
26: end if
```

#### Comparison with Implementation:

#### 1. Congestion Differentiation (Fabric vs. Endpoint)
- **Paper:** The switch determines congestion type by checking the port's neighbor. If connected to another switch, it is **Fabric Congestion** (triggering BECN to sender for multipath routing). If connected to an end host, it is **Endpoint Congestion** (triggering forward ECN marking to receiver).
- **Codebase:** `FlowStarSwitchAgent` only monitors local queue occupancy (`occupancy > m_becnThreshold`). It does not inspect the next-hop node type. It sends BECNs directly to the sender for any queue buildup.

#### 2. ECN Marking & CNP Generation
- **Paper:** The switch marks forward packets with ECN. The receiver calculates `recvRate` and responds with a CNP carrying `recvRate` in the 24-bit PSN field.
- **Codebase:** `CbfcQueueDisc` contains no logic to mark ECN tags on packets. In `FlowStarReceiver::HandleRead`, `ecnMarked` evaluates to false. The receiver instead invokes `m_endpointController->ShouldGenerateCnp()`, which generates a CNP only if the receiver's measured throughput falls below $80\%$ of expected line rate.

#### 3. Rate Decrease on CNP
- **Paper:** Sender sets `currRate = recvRate`, `CFlag = 1`, and $\alpha = 1/64$.
- **Codebase:** `FlowStarRateController::OnCnp` sets `currentRate = receivingRate * m_cnpDecreaseFactor` and switches state to `SLOW_RECOVERY`. It does not set `CFlag` or $\alpha$.

#### 4. Rate Recovery Strategy
- **Paper:** Uses exponential smoothing towards line rate:
  $$currRate = lineRate \times \alpha + currRate \times (1 - \alpha)$$
  where $\alpha$ doubles every period ($1/64, 1/32, 1/16, 1/8, 1/4, 1/2, 1$). This creates a **slow-first, fast-later** aggressive recovery that gently probes the bottleneck for 3 RTTs and then quickly reclaims bandwidth over 7 RTTs total.
- **Codebase:** Implements a custom piecewise state machine:
  - `SLOW_RECOVERY`: Additive Increase ($currRate += 100\text{ Mbps}$) every 50 $\mu$s until reaching $50\%$ of line rate.
  - `AGGRESSIVE_RECOVERY`: Proportional step ($currRate += (lineRate - currRate) \times 0.1$).
  - **Verdict:** This is standard AIMD/proportional pacing, **not** the mathematical formulation of FlowStar Algorithm 2.

#### 5. BECN Handling
- **Paper:** Section IV-B(1) explicitly states: *"When detecting fabric congestion, the switch generates BECN direct feedback to the source CA. This helps CA sense the congestion inside the network faster and enables load balancing... Neither message needs to be slowed down because there are other free paths available in the fabric."* (Line 24–26: `if receive BECN then Enable load balancing`).
- **Codebase:** In `FlowStarRateController::OnBecn`, the sender executes:
  ```cpp
  DataRate newRate (it->second.currentRate.GetBitRate () * m_becnDecreaseFactor); // Multiplicative Decrease: cuts rate by 50%
  it->second.currentRate = newRate;
  it->second.state = SLOW_RECOVERY;
  ```
  **Verdict:** Throttling the sender upon receiving a BECN directly contradicts the fundamental principle of the paper.

---

## 4. Evaluation of the Four Proposed Improvements

The repository introduced four custom improvements beyond the baseline FlowStar design. Here is their functional audit:

### 4.1 Improvement 1: Congestion-Aware Dynamic Queue Assignment (`ImprovedCbfcQueueDisc`)
* **Design Goal:** When dedicated queues are exhausted, score candidate shared queues using a composite metric:
  $$Score = Occupancy + 4 \times ECN + 8 \times BECN + 16 \times Pause$$
* **Audit Findings:**
  - Class `ImprovedCbfcQueueDisc` inherits from `CbfcQueueDisc` and overrides `AssignQueue()`.
  - The standalone unit test `tests/improvement1-dqa-test.cc` passes because it manually invokes `SetQueueCongestionSignals()`.
  - **Critical Failure in Simulation:** Neither the switch agent nor the queue disc ever calls `SetQueueCongestionSignals()` during simulation runs. In `phase5-evaluation.cc`, `ecnEvents`, `becnEvents`, and `pauseEvents` remain permanently 0. Thus:
    $$Score = Occupancy + 0 + 0 + 0 = Occupancy$$
  - The improved DQA reduces entirely to the base DQA least-occupancy check. It has **zero effect** on simulation results.

### 4.2 Improvement 2: Hybrid Per-Flow State & Metadata Lifecycle
* **Design Goal:** Decouple physical queue allocations from logical flow tracking (`FlowMetadata`), allowing independent credit enforcement on shared queues and safe flow cleanup/reuse.
* **Audit Findings:**
  - `FlowMetadata` and `m_flowMetadata` were embedded directly into the base `CbfcQueueDisc` class rather than a distinct improvement subclass.
  - The unit test `tests/improvement2-hybrid-state-test.cc` validates that calling `disc->RemoveFlow()` frees queue slots.
  - **Critical Failure in Simulation:** No application or simulation script ever invokes `RemoveFlow()` when flows finish. In `scripts/run-final-evaluation.py`, Mode F1 (`useI1`) and Mode F2 (`useI2`) yield identical metrics across all seeds:
    - Throughput: `96,000,000 bps` (identical)
    - Max Queue: `160 packets` (identical)
    - Average Queue: `41.2 packets` (identical)
    - Average FCT: `3,818,448 ns` (identical)
  - Improvement 2 provides **no measurable behavioral difference** in the evaluation suite.

### 4.3 Improvement 3: Adaptive Multipath Routing (`FlowStarPathManager`)
* **Design Goal:** Track congestion per network path IP upon BECN receipt, and dynamically migrate active flows to alternate paths if congestion exceeds a threshold after a cooldown interval.
* **Audit Findings:**
  - `FlowStarPathManager` implements path registration, exponential score decay, threshold comparisons, and path migration.
  - Senders in `FlowStarSender::HandleBecn` query `m_pathManager->GetAdaptivePath()` and reconnect the UDP socket to the alternate IP.
  - All unit tests (`tests/adaptive-routing-test.cc`, `tests/improvement3-adaptive-routing-test.cc`) pass with 100% assertions met.
  - **Limitation:** Improvement 3 is completely excluded from the Stage F final evaluation script (`scripts/run-final-evaluation.py` only runs B0–B2 and F0–F2; Mode 6 is omitted).

### 4.4 Improvement 4: Congestion-Aware Rate Recovery (`ImprovedFlowStarRateController`)
* **Design Goal:** Modulate recovery interval and additive step dynamically based on congestion severity ($Severity = \min(1.0, Occupancy / 100)$).
* **Audit Findings:**
  - `ImprovedFlowStarRateController` adjusts pacing delay ($Delay = Interval \times (0.5 + 1.5 \times Severity)$) and scales additive increase steps.
  - Unit tests (`tests/improvement4-recovery-test.cc`) pass with valid assertions.
  - **Limitation:** It is built on top of the custom AIMD controller rather than Algorithm 2's $\alpha$-doubling formula, and it was excluded from the final evaluation runner.

---

## 5. Experimental Methodology & Results Integrity Audit

### 5.1 Topology & Workload Discrepancies

| Aspect | Research Paper Setup | Repository Setup | Impact |
| :--- | :--- | :--- | :--- |
| **Simulator Platform** | OMNeT++ with Mellanox InfiniBand Flit-Level Model | ns-3.48 with standard IP/UDP packet models | Omits InfiniBand cut-through flit timing, credits, and link headers |
| **Network Scale** | Dragonfly+ (1088 nodes, 17 groups) & Fat-tree (128 nodes, 8 pods) | 2–3 host senders, 1 receiver, 2 switches (Dumbbell) | Cannot evaluate multi-hop congestion spreading or Dragonfly fabric routing |
| **Link Data Rates** | 4xQDR InfiniBand (32 Gbps effective speed, 256 B MTU) | 10 Gbps edge links, 1 Gbps / 5 Gbps bottleneck (1000 B packets) | Pacing and credit timing do not match paper hardware scale |
| **Workload Profile** | 70% small MPI bursts (<16 KB) mixed with 8 MB background I/O (10%) | Fixed homogeneous UDP packet streams (2,000 or 10,000 pkts) | Does not test incast latency degradation on short MPI messages |
| **Traffic Patterns** | Uniform random, Adversarial pattern, Real AMG HPC trace | Continuous line-rate bursts without stochastic inter-arrival spacing | Cannot evaluate P99 tail latency under realistic load distributions |

### 5.2 The Throughput Calculation Bug in `run-final-evaluation.py`

In `scripts/run-final-evaluation.py`, line 115 computes throughput as follows:
```python
throughput_bps = f"{rx * 1000 * 8:.0f}"
```
- `rx` is the total count of packets received across all hops during the run.
- Multiplying by 1000 bytes and 8 bits yields **total bits received**, NOT bits per second!
- The calculation **does not divide by simulation duration or flow completion time**.
- Furthermore, the evaluation compared configurations that ran completely different binaries with disparate packet counts:
  - **F0** executed `phase4-bottleneck` (3 senders transmitting 10,000 packets for 3 seconds $\to$ 268,026 total hop receptions $\to 268,026 \times 8000 = \mathbf{2,144,208,000}$).
  - **F1 / F2** executed `phase5-evaluation` (2 senders transmitting 2,000 packets $\to$ 12,000 total hop receptions $\to 12,000 \times 8000 = \mathbf{96,000,000}$).
  - **B0 / B1** executed `phase2-no-control` (3 senders transmitting 1,000 packets $\to$ 9,000 total hop receptions $\to 9,000 \times 8000 = \mathbf{72,000,000}$).
  - **B2** executed `phase3-cbfc-comparison` (18,000 total hop receptions $\to 18,000 \times 8000 = \mathbf{144,000,000}$).

**Conclusion:** The reported "2.14 Gbps vs 96 Mbps" throughput comparison in `final_report.md` is an artifact of multiplying different packet counts by 8000, rather than an actual throughput measurement.

### 5.3 Determinism and Lack of Statistical Variation

In `results/final/comparison.csv`, Seeds 1, 2, and 3 produce identical numbers for every single mode:
```csv
B0,1,1,72000000,0,2997,PASS,NOT AVAILABLE
B0,2,1,72000000,0,2997,PASS,NOT AVAILABLE
B0,3,1,72000000,0,2997,PASS,NOT AVAILABLE
```
Because traffic generation uses fixed deterministic schedules without Poisson inter-arrivals or random start offsets, the multi-seed evaluation produces zero variance.

---

## 6. What Is Working Well in the Project

Despite the deviations from the paper, the codebase possesses several well-engineered components:
1. **Compilation and Stability:** Clean compilation under GCC/Clang with C++17 inside ns-3.48; all 23 test targets build and execute without segmentation faults or runtime errors.
2. **Per-Flow Queuing & Round-Robin Scheduler:** `CbfcQueueDisc` correctly instantiates multiple internal queues, classifies packets by MID, assigns dedicated queues for initial flows, and round-robins across active queues.
3. **Pacing and Event Scheduling:** `FlowStarSender` cleanly implements rate pacing using `Simulator::Schedule()` based on `CalculateBytesTxTime()`.
4. **Adaptive Routing Logic (I3):** `FlowStarPathManager` and its socket migration logic in `FlowStarSender::HandleBecn` correctly maintain path congestion state and rebind destinations upon sustained congestion.
5. **Lossless Forwarding:** Across all properly configured simulations, buffer limits and pacing successfully prevent packet drops.

---

## 7. Actionable Remediation Roadmap

To bring the `FlowStar-NS3` implementation into genuine fidelity with the research paper, the following engineering steps should be undertaken:

### Step 1: Implement Algorithm 1 Faithfully (DQA)
1. Extend `FlowStarMidTag` to include `uint32_t seq` and `uint32_t totalPackets`.
2. In `CbfcQueueDisc::DoEnqueue`:
   - If `seq == 1`, assign to `emptyQ.random` (or `QT.min` if full), increment `QT[q]`.
   - If `seq == totalPackets`, mark the item as the final packet.
3. In `CbfcQueueDisc::DoDequeue`:
   - When the final packet of an MID is dequeued, decrement `QT[q]` and call `m_messageTable.erase(mid)`. This enables real dynamic queue reuse.

### Step 2: Implement Algorithm 2 Rate Regulation Accurately
1. **Correct BECN Behavior:** Remove the multiplicative decrease (`m_becnDecreaseFactor`) in `FlowStarRateController::OnBecn`. When a BECN is received, do not reduce transmission rate; instead, trigger path migration via `FlowStarPathManager`.
2. **Implement Algorithm 2 Rate Recovery:** Replace the AIMD state machine with the paper's exact formula:
   ```cpp
   if (currRate < lineRate && cFlag == 1) {
       currRate = lineRate * alpha + currRate * (1.0 - alpha);
       alpha = std::min(1.0, alpha * 2.0);
   }
   if (currRate >= lineRate) {
       cFlag = 0;
   }
   ```
   Initialize $\alpha_{initial} = 1.0 / 64.0$ upon CNP receipt.

### Step 3: Implement Switch Congestion Differentiation & ECN Marking
1. In `CbfcQueueDisc` or `FlowStarSwitchAgent`, inspect the downstream NetDevice.
   - If connected to a switch node $\to$ Fabric Congestion $\to$ send BECN back to source.
   - If connected to an end-host node $\to$ Endpoint Congestion $\to$ mark the forward packet with `EcnTag (CongestionExperienced = true)`.
2. In `FlowStarReceiver`, generate CNPs strictly upon receiving packets with `EcnTag` set, carrying the measured `recvRate`.

### Step 4: Fix Evaluation Pipeline & Topologies
1. In `scripts/run-final-evaluation.py`, compute true throughput:
   $$\text{Throughput (bps)} = \frac{\text{rx\_bytes} \times 8}{\text{FCT or Duration (seconds)}}$$
2. Standardize traffic parameters across all compared modes (identical host count, packet size, and total bytes).
3. Introduce exponential / Poisson inter-arrival times to evaluate performance across varied load rates ($\rho \in [0.1, 0.9]$), reproducing the paper's latency vs. load curves.
4. Wire all control sockets (`RegisterCreditManager`, `RegisterSenderCredit`, `RegisterSenderCnp`, `RegisterSenderBecn`) inside `phase5-evaluation.cc`.
