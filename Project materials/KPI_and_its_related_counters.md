# LTE KPI Degradation Analyzer
## Complete KPI & Related Columns Reference

**Project:** Graduation Project - RF Optimization Analysis  
**Version:** 2.0 (Enhanced with TA Distribution, CEU Metrics, CA Enhanced)  
**Last Updated:** 2024

---

## Table of Contents

1. [Overview](#overview)
2. [Identifier Columns](#identifier-columns)
3. [KPI Configurations](#kpi-configurations)
   - [DL Traffic](#1-dl-traffic)
   - [UL Traffic](#2-ul-traffic)
   - [DL Throughput](#3-dl-throughput)
   - [UL Throughput](#4-ul-throughput)
   - [RRC Setup Success Rate](#5-rrc-setup-success-rate)
   - [ERAB Setup Success Rate](#6-erab-setup-success-rate)
   - [Drop Rate](#7-drop-rate)
   - [HO Success Rate](#8-ho-success-rate)
   - [Availability](#9-availability)
   - [RACH Success Rate](#10-rach-success-rate)
   - [CSFB KPI](#11-csfb-kpi)
   - [VoLTE KPIs](#12-volte-kpis)
   - [RRC Re-establishment](#13-rrc-re-establishment)
4. [Feature Categories Summary](#feature-categories-summary)
5. [Statistics](#statistics)

---

## Overview

This document provides a complete reference of all KPIs (Key Performance Indicators) and their related columns/features used in the LTE KPI Degradation Analyzer. The system analyzes network performance degradation and identifies root causes through correlated counter analysis.

### How to Use This Document

- **Target KPI**: The main metric being analyzed for degradation
- **Bad Direction**: `low` means degradation when value drops; `high` means degradation when value increases
- **Threshold**: Percentage change that triggers detection
- **Severity**: 1 (Low) to 5 (Critical) - Used for cause prioritization
- **Category**: Classification of the root cause type
- **Reason**: Description of why this feature indicates degradation
- **Recommended Action**: RF optimization actions to investigate

---

## Identifier Columns

These columns are used for cell identification and are required in all data files:

| Column Name | Description | Usage |
|-------------|-------------|-------|
| `Date` | Time dimension for analysis | Required |
| `eNodeB Name` | Site identification | Required |
| `Cell Name` | Cell identification | Required |
| `LocalCell Id` | Local cell ID | Required |
| `Cluster` | Cluster grouping | Optional |
| `Cell FDD TDD Indication` | FDD/TDD mode | Optional |
| `Downlink EARFCN` | Frequency information | Optional |

---

## KPI Configurations

---

### 1. DL Traffic

**Target KPI:** `(HU) DL Traffic Volume (GBytes)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `30%`  
**Category:** Traffic  
**Minimum Baseline Value:** `1.0 GBytes`

#### Related Features (24 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `(HU) Cell DL Average Throughput (Mbps)` | low | 20% | 3 | DL Throughput Degradation |
| 2 | `(HU) User DL Average Throughput (Mbps)` | low | 20% | 3 | User Throughput Degradation |
| 3 | `(HU) DL PRB Utilization(%)` | high | 20% | 2 | Capacity / Congestion |
| 4 | `DL Average CQI` | low | 15% | 3 | Radio Quality Issue |
| 5 | `(HU) DL IBLER(%)` | high | 20% | 3 | DL Radio Quality Issue |
| 6 | `DL RBLER` | high | 20% | 4 | DL Radio Failure |
| 7 | `(HU) PDSCH MCS` | low | 15% | 2 | Poor Modulation Efficiency |
| 8 | `Availability` | low | 1% | 5 | Availability Issue |
| 9 | `(HU) Cell Unavail Time (s)` | high | 20% | 5 | Cell Unavailability |
| 10 | `L.Traffic.ActiveUser.Dl.Avg` | low | 20% | 1 | Traffic Demand Drop |
| 11 | `MAC CA Traffic Ratio` | low | 20% | 2 | Carrier Aggregation Issue |
| 12 | `DL Traffic QCI-9` | low | 20% | 2 | Default Bearer Traffic Drop |
| 13 | `DL_CCE_AllocFail (%)` | high | 20% | 3 | Control Channel Congestion |
| 14 | `6.6-14 km` | high | 20% | 3 | Extended Coverage Issue |
| 15 | `3.5-6.6 km` | high | 20% | 2 | Cell Edge Users Increase |
| 16 | `TA Weighted Avg (meter)` | high | 20% | 2 | Average Distance Increase |
| 17 | `(HU)CEU Cell Downlink Average Throughput` | low | 20% | 3 | Cell Edge Throughput |
| 18 | `(HU)CEU User Downlink Average Througput` | low | 20% | 3 | CEU User Experience |
| 19 | `L.Traffic.User.BorderUE.Avg` | high | 20% | 2 | Border UE Increase |
| 20 | `L.CA.UE.Avg` | low | 20% | 2 | CA User Drop |
| 21 | `L.CA.DLSCell.Act.Att` | low | 20% | 2 | SCell Activation Issue |
| 22 | `L.CA.DLSCell.Add.Att` | low | 20% | 2 | SCell Addition Issue |
| 23 | `3CC DL PDCP CA Traffic Volume GB` | low | 20% | 2 | 3CC CA Traffic Drop |
| 24 | `DL PDCP FDDTDD CA Traffic Volume GB` | low | 20% | 2 | FDD-TDD CA Traffic Drop |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `(HU) Cell DL Average Throughput (Mbps)` | Cell DL throughput decreased. | Check DL scheduler, bandwidth, CA activation, load balancing, and congestion. |
| `(HU) User DL Average Throughput (Mbps)` | User DL throughput decreased. | Check radio quality, PRB load, scheduler behavior, and user distribution. |
| `(HU) DL PRB Utilization(%)` | DL PRB utilization increased. | Check load balancing, CA usage, bandwidth, traffic distribution, and capacity expansion. |
| `DL Average CQI` | DL CQI decreased. | Check interference, PCI conflict/confusion, antenna tilt, azimuth, and coverage. |
| `(HU) DL IBLER(%)` | DL IBLER increased. | Check interference, CQI, MCS, antenna tilt, and DL power. |
| `DL RBLER` | DL RBLER increased. | Check DL interference, poor coverage, CQI, MCS, and radio conditions. |
| `(HU) PDSCH MCS` | PDSCH MCS decreased. | Check CQI, SINR, interference, antenna direction, and coverage. |
| `Availability` | Cell availability decreased. | Check alarms, S1 issue, manual outage, system outage, and site availability. |
| `(HU) Cell Unavail Time (s)` | Cell unavailable time increased. | Check site outage, power issue, transmission issue, S1 failure, and alarms. |
| `L.Traffic.ActiveUser.Dl.Avg` | DL active users decreased. | Validate if traffic drop is normal demand behavior before RF optimization. |
| `MAC CA Traffic Ratio` | CA traffic ratio decreased. | Check CA activation, SCell availability, CA bands, and CA parameters. |
| `DL Traffic QCI-9` | QCI-9 DL traffic decreased. | Check packet data service, APN/data service, user demand, and internet traffic trend. |
| `DL_CCE_AllocFail (%)` | DL CCE allocation failure increased. | Check PDCCH/CCE utilization, control channel capacity, and scheduler configuration. |
| `6.6-14 km` | High TA bin indicates users at cell edge or beyond planned coverage. | Check coverage extension, overshooting, pilot pollution, and cell size. |
| `3.5-6.6 km` | Users at cell edge increased. | Check coverage, cell dominance, and neighbor relationships. |
| `TA Weighted Avg (meter)` | Average user distance from site increased. | Check coverage shift, antenna tilt, and traffic migration. |
| `(HU)CEU Cell Downlink Average Throughput` | Cell edge user throughput degraded. | Check CEU scheduling, cell edge SINR, and coverage. |
| `(HU)CEU User Downlink Average Througput` | Cell edge user experience degraded. | Check CEU parameters, ICIC, and edge coverage. |
| `L.Traffic.User.BorderUE.Avg` | Border/cell edge users increased. | Check coverage overlap, handover zones, and cell dominance. |
| `L.CA.UE.Avg` | Average CA users decreased. | Check CA activation, SCell availability, and CA parameters. |
| `L.CA.DLSCell.Act.Att` | SCell activation attempts decreased. | Check SCell configuration, CA licensing, and secondary carriers. |
| `L.CA.DLSCell.Add.Att` | SCell addition attempts decreased. | Check CA configuration and inter-frequency measurements. |
| `3CC DL PDCP CA Traffic Volume GB` | 3-carrier aggregation traffic decreased. | Check 3CC CA bands, SCell availability, and CA configuration. |
| `DL PDCP FDDTDD CA Traffic Volume GB` | FDD-TDD carrier aggregation traffic decreased. | Check FDD-TDD CA configuration and cross-mode scheduling. |

---

### 2. UL Traffic

**Target KPI:** `(HU) UL Traffic Volume (GBytes)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `30%`  
**Category:** Traffic  
**Minimum Baseline Value:** `0.1 GBytes`

#### Related Features (13 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `(HU) Cell UL Average Throughput (Mbps)` | low | 20% | 3 | UL Throughput Degradation |
| 2 | `(HU) User UL Average Throughput (Mbps)` | low | 20% | 3 | UL User Throughput Degradation |
| 3 | `(HU)UL PRB Utilization(%)` | high | 20% | 2 | UL Capacity / Congestion |
| 4 | `(HU) Avg UL Interference(dBm)` | high | 10% | 4 | UL Interference Issue |
| 5 | `L.UpPTS.Interference.Avg(dBm)` | high | 10% | 3 | UL Interference Issue |
| 6 | `(HU) UL IBLER(%)` | high | 20% | 3 | UL Radio Quality Issue |
| 7 | `UL RBLER` | high | 20% | 4 | UL Radio Failure |
| 8 | `(HU) PUSCH MCS` | low | 15% | 2 | UL Modulation Efficiency Issue |
| 9 | `L.Traffic.ActiveUser.UL.Avg` | low | 20% | 1 | UL Traffic Demand Drop |
| 10 | `6.6-14 km` | high | 20% | 3 | UL Coverage Extension |
| 11 | `TA Weighted Avg (meter)` | high | 20% | 2 | UL Distance Increase |
| 12 | `(HU)CEU Cell Uplink Average Throughput` | low | 20% | 3 | UL Cell Edge Throughput |
| 13 | `(HU)CEU User Uplink Average Throughput` | low | 20% | 3 | UL CEU User Experience |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `(HU) Cell UL Average Throughput (Mbps)` | Cell UL throughput decreased. | Check UL scheduler, UL PRB utilization, uplink interference, and power control. |
| `(HU) User UL Average Throughput (Mbps)` | User UL throughput decreased. | Check UL radio quality, UL interference, PUSCH MCS, and UL PRB load. |
| `(HU)UL PRB Utilization(%)` | UL PRB utilization increased. | Check UL capacity, UL scheduling, uplink load, and traffic distribution. |
| `(HU) Avg UL Interference(dBm)` | Average UL interference increased. | Check external interference, PIM, neighboring cells, and uplink noise rise. |
| `L.UpPTS.Interference.Avg(dBm)` | UpPTS interference increased. | Check uplink interference source and TDD interference conditions. |
| `(HU) UL IBLER(%)` | UL IBLER increased. | Check UL interference, PUSCH MCS, UE power, and coverage. |
| `UL RBLER` | UL RBLER increased. | Check UL interference, coverage, UE power, and uplink radio conditions. |
| `(HU) PUSCH MCS` | PUSCH MCS decreased. | Check UL SINR, interference, UE power control, and uplink coverage. |
| `L.Traffic.ActiveUser.UL.Avg` | UL active users decreased. | Validate traffic trend before applying RF action. |
| `6.6-14 km` | UL users at extended range. | Check UL coverage, UE power, and path balance. |
| `TA Weighted Avg (meter)` | UL users average distance increased. | Check UL coverage and path balance. |
| `(HU)CEU Cell Uplink Average Throughput` | Cell edge UL throughput degraded. | Check UL CEU scheduling and edge coverage. |
| `(HU)CEU User Uplink Average Throughput` | Cell edge UL user experience degraded. | Check UL power control and CEU parameters. |

---

### 3. DL Throughput

**Target KPI:** `(HU) User DL Average Throughput (Mbps)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `20%`  
**Category:** Integrity  
**Minimum Baseline Value:** `5.0 Mbps`

#### Related Features (14 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `(HU) DL PRB Utilization(%)` | high | 20% | 3 | DL Congestion |
| 2 | `DL Average CQI` | low | 15% | 4 | Poor Radio Quality |
| 3 | `(HU) DL IBLER(%)` | high | 20% | 4 | High DL Retransmission |
| 4 | `DL RBLER` | high | 20% | 4 | DL Radio Block Errors |
| 5 | `(HU) PDSCH MCS` | low | 15% | 3 | Low DL Modulation |
| 6 | `MAC CA Traffic Ratio` | low | 20% | 2 | Low CA Usage |
| 7 | `L.Traffic.ActiveUser.Dl.Avg` | high | 20% | 2 | High User Load |
| 8 | `6.6-14 km` | high | 20% | 3 | Cell Edge Impact on Throughput |
| 9 | `0-156 m` | low | 20% | 2 | Near Users Drop |
| 10 | `(HU)CEU Cell Downlink Average Throughput` | low | 20% | 4 | CEU Throughput Impact |
| 11 | `(HU)CEU User Downlink Average Througput` | low | 20% | 4 | CEU User Impact |
| 12 | `Reported rank 2 (%)` | low | 15% | 2 | MIMO Efficiency Drop |
| 13 | `CQI_CW0` | low | 15% | 3 | CQI Codeword 0 Drop |
| 14 | `CQI_CW1` | low | 15% | 3 | CQI Codeword 1 Drop |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `(HU) DL PRB Utilization(%)` | DL PRB utilization increased while DL throughput decreased. | Check congestion, load balancing, CA, bandwidth, scheduler, and capacity expansion. |
| `DL Average CQI` | CQI decreased while DL throughput degraded. | Check interference, PCI, antenna tilt, azimuth, and coverage. |
| `(HU) DL IBLER(%)` | DL IBLER increased while DL throughput degraded. | Check BLER, CQI, MCS, DL power, and interference. |
| `DL RBLER` | DL RBLER increased while DL throughput degraded. | Check interference, radio quality, and coverage. |
| `(HU) PDSCH MCS` | PDSCH MCS decreased while DL throughput degraded. | Check CQI, SINR, interference, and coverage. |
| `MAC CA Traffic Ratio` | CA traffic ratio decreased while DL throughput degraded. | Check CA activation, SCell availability, and CA configuration. |
| `L.Traffic.ActiveUser.Dl.Avg` | DL active users increased while DL throughput decreased. | Check load, scheduling, congestion, and user distribution. |
| `6.6-14 km` | Distant users impacting throughput. | Check coverage, user distribution, and edge scheduling. |
| `0-156 m` | Near-cell users decreased. | Check traffic distribution and near-cell coverage. |
| `(HU)CEU Cell Downlink Average Throughput` | Cell edge throughput impacting overall. | Check CEU scheduling and SINR. |
| `(HU)CEU User Downlink Average Througput` | CEU user throughput degraded. | Check CEU parameters and coverage. |
| `Reported rank 2 (%)` | Rank 2 (MIMO) usage decreased. | Check MIMO conditions, correlation, and rank adaptation. |
| `CQI_CW0` | CQI on codeword 0 degraded. | Check channel conditions and reporting. |
| `CQI_CW1` | CQI on codeword 1 (MIMO) degraded. | Check MIMO channel conditions. |

---

### 4. UL Throughput

**Target KPI:** `(HU) User UL Average Throughput (Mbps)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `20%`  
**Category:** Integrity  
**Minimum Baseline Value:** `2.0 Mbps`

#### Related Features (8 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `(HU)UL PRB Utilization(%)` | high | 20% | 3 | UL Congestion |
| 2 | `(HU) Avg UL Interference(dBm)` | high | 10% | 4 | UL Interference Issue |
| 3 | `(HU) UL IBLER(%)` | high | 20% | 4 | High UL Retransmission |
| 4 | `UL RBLER` | high | 20% | 4 | UL Radio Block Errors |
| 5 | `(HU) PUSCH MCS` | low | 15% | 3 | Low UL Modulation |
| 6 | `L.Traffic.ActiveUser.UL.Avg` | high | 20% | 2 | High UL User Load |
| 7 | `6.6-14 km` | high | 20% | 3 | UL Distance Impact |
| 8 | `(HU)CEU Cell Uplink Average Throughput` | low | 20% | 4 | UL CEU Impact |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `(HU)UL PRB Utilization(%)` | UL PRB utilization increased while UL throughput degraded. | Check UL load, UL scheduler, and uplink capacity. |
| `(HU) Avg UL Interference(dBm)` | UL interference increased while UL throughput degraded. | Check external interference, PIM, and uplink noise rise. |
| `(HU) UL IBLER(%)` | UL IBLER increased while UL throughput degraded. | Check UL BLER, interference, PUSCH MCS, and UE power. |
| `UL RBLER` | UL RBLER increased while UL throughput degraded. | Check UL coverage, interference, and UE power limitation. |
| `(HU) PUSCH MCS` | PUSCH MCS decreased while UL throughput degraded. | Check uplink SINR, interference, and power control. |
| `L.Traffic.ActiveUser.UL.Avg` | UL active users increased while UL throughput decreased. | Check uplink scheduling, congestion, and load distribution. |
| `6.6-14 km` | Distant UL users impacting throughput. | Check UL path loss and power headroom. |
| `(HU)CEU Cell Uplink Average Throughput` | Cell edge UL throughput impacting overall. | Check UL CEU scheduling. |

---

### 5. RRC Setup Success Rate

**Target KPI:** `(TE) RRC Setup SR%`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** Accessibility  
**Minimum Baseline Value:** `90%`

#### Related Features (8 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `L.RRC.ConnReq.Att` | high | 20% | 2 | High RRC Attempts |
| 2 | `RRC Setup Failure Time` | high | 20% | 4 | RRC Failure Increase |
| 3 | `L.RRC.SetupFail.NoReply` | high | 20% | 4 | RRC No Reply |
| 4 | `L.RRC.SetupFail.Rej` | high | 20% | 3 | RRC Rejection |
| 5 | `L.RRC.SetupFail.Rej.MMEOverload` | high | 20% | 4 | MME Overload |
| 6 | `L.RRC.SetupFail.ResFail` | high | 20% | 4 | Radio Resource Failure |
| 7 | `RACH Contention-Based Failures` | high | 20% | 3 | RACH Failure |
| 8 | `RACH Non-Contention-Based SR` | low | 5% | 3 | Non-Contention RACH Issue |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `L.RRC.ConnReq.Att` | RRC attempts increased. | Check RACH load, access parameters, admission control, and overload. |
| `RRC Setup Failure Time` | RRC setup failures increased. | Check RACH failures, no reply, rejection, admission control, and radio quality. |
| `L.RRC.SetupFail.NoReply` | RRC no-reply failures increased. | Check coverage, interference, RACH configuration, and UE access conditions. |
| `L.RRC.SetupFail.Rej` | RRC rejection failures increased. | Check admission control, overload, forbidden access, and MME overload. |
| `L.RRC.SetupFail.Rej.MMEOverload` | RRC rejection due to MME overload increased. | Check MME/S1 signaling, core side load, and S1 interface. |
| `L.RRC.SetupFail.ResFail` | RRC setup failures due to resource failure increased. | Check radio resources, PRB load, admission control, and congestion. |
| `RACH Contention-Based Failures` | RACH contention failures increased. | Check PRACH configuration, root sequence planning, preamble load, and coverage. |
| `RACH Non-Contention-Based SR` | Non-contention RACH SR degraded. | Check HO-related RACH and dedicated preambles. |

---

### 6. ERAB Setup Success Rate

**Target KPI:** `ERAB Setup Success Rate`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** Accessibility  
**Minimum Baseline Value:** `95%`

#### Related Features (6 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `L.E-RAB.AttEst` | high | 20% | 2 | High ERAB Attempts |
| 2 | `ERAB Setup Failure Times` | high | 20% | 4 | ERAB Failure Increase |
| 3 | `L.E-RAB.FailEst.NoRadioRes` | high | 20% | 4 | No Radio Resource |
| 4 | `L.E-RAB.FailEst.NoReply` | high | 20% | 3 | No Reply Failure |
| 5 | `L.E-RAB.FailEst.MME` | high | 20% | 4 | MME Related Failure |
| 6 | `L.E-RAB.FailEst.TNL` | high | 20% | 4 | Transport Network Failure |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `L.E-RAB.AttEst` | E-RAB setup attempts increased. | Check access load, service attempts, and admission control. |
| `ERAB Setup Failure Times` | E-RAB setup failures increased. | Check ERAB failure reason counters, MME, TNL, RNL, and radio resources. |
| `L.E-RAB.FailEst.NoRadioRes` | E-RAB failures due to no radio resources increased. | Check PRB load, admission control, congestion, and capacity. |
| `L.E-RAB.FailEst.NoReply` | E-RAB no-reply failures increased. | Check radio quality, signaling, and UE response issues. |
| `L.E-RAB.FailEst.MME` | E-RAB setup failures related to MME increased. | Check MME/core side, S1 signaling, and core load. |
| `L.E-RAB.FailEst.TNL` | E-RAB setup failures related to TNL increased. | Check transmission, backhaul, S1-U/S1-C, and transport path. |

---

### 7. Drop Rate

**Target KPI:** `E-RAB Drop Rate (E-NodeB + MME) %`  
**Bad Direction:** `high` (Degradation when value increases)  
**Default Threshold:** `20%`  
**Category:** Retainability  
**Minimum Baseline Value:** `0.1%`

#### Related Features (15 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `L.E-RAB.AbnormRel` | high | 20% | 5 | Abnormal Release Increase |
| 2 | `L.E-RAB.AbnormRel.Radio` | high | 20% | 5 | Radio Drop Issue |
| 3 | `L.E-RAB.AbnormRel.Radio.ULSyncFail` | high | 20% | 5 | UL Sync Failure |
| 4 | `L.E-RAB.AbnormRel.Radio.UuNoReply` | high | 20% | 4 | Uu No Reply |
| 5 | `L.E-RAB.AbnormRel.TNL` | high | 20% | 4 | Transport Drop Issue |
| 6 | `L.E-RAB.AbnormRel.MME` | high | 20% | 4 | MME Drop Issue |
| 7 | `L.E-RAB.AbnormRel.HOFailure` | high | 20% | 4 | HO Related Drop |
| 8 | `RRC Connection Drop Rate%` | high | 20% | 5 | RRC Drop Issue |
| 9 | `(HU) RRC Reestablish Ratio(%)` | high | 20% | 4 | High Re-establishment |
| 10 | `RRC Reestablish Failures(times)` | high | 20% | 4 | Re-establishment Failures |
| 11 | `L.RRC.ReEstFail.NoReply` | high | 20% | 3 | Re-establishment No Reply |
| 12 | `L.RRC.ReEstFail.Rej` | high | 20% | 3 | Re-establishment Rejection |
| 13 | `L.E-RAB.AbnormRel.eNBTot.UEAbnormal` | high | 20% | 4 | UE Abnormal Release |
| 14 | `L.E-RAB.AbnormRel.Radio.DRBReset` | high | 20% | 4 | DRB Reset |
| 15 | `L.E-RAB.AbnormRel.Radio.SRBReset` | high | 20% | 4 | SRB Reset |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `L.E-RAB.AbnormRel` | E-RAB abnormal releases increased. | Check drop reason counters, radio quality, HO failures, and TNL/MME causes. |
| `L.E-RAB.AbnormRel.Radio` | Radio abnormal releases increased. | Check coverage, interference, CQI, BLER, and antenna settings. |
| `L.E-RAB.AbnormRel.Radio.ULSyncFail` | Drops due to UL synchronization failure increased. | Check uplink coverage, UL interference, UE power, and timing advance. |
| `L.E-RAB.AbnormRel.Radio.UuNoReply` | Drops due to Uu no-reply increased. | Check coverage holes, interference, and radio link quality. |
| `L.E-RAB.AbnormRel.TNL` | Transport-related abnormal releases increased. | Check backhaul, transmission alarms, packet loss, and transport congestion. |
| `L.E-RAB.AbnormRel.MME` | MME-related abnormal releases increased. | Check core network, MME, S1 signaling, and S1 reset counters. |
| `L.E-RAB.AbnormRel.HOFailure` | Abnormal releases related to HO failure increased. | Check neighbors, missing neighbors, A3 offset, CIO, TTT, and PCI issues. |
| `RRC Connection Drop Rate%` | RRC connection drop rate increased. | Check radio quality, coverage, interference, re-establishment, and mobility. |
| `(HU) RRC Reestablish Ratio(%)` | RRC re-establishment ratio increased. | Check radio link failures and re-establishment triggers. |
| `RRC Reestablish Failures(times)` | RRC re-establishment failures increased. | Check coverage and RLF causes. |
| `L.RRC.ReEstFail.NoReply` | Re-establishment no reply failures. | Check coverage and signaling. |
| `L.RRC.ReEstFail.Rej` | Re-establishment rejections increased. | Check network admission and context. |
| `L.E-RAB.AbnormRel.eNBTot.UEAbnormal` | UE abnormal releases increased. | Check UE behavior and radio conditions. |
| `L.E-RAB.AbnormRel.Radio.DRBReset` | DRB reset drops increased. | Check DRB integrity and radio link. |
| `L.E-RAB.AbnormRel.Radio.SRBReset` | SRB reset drops increased. | Check signaling radio bearer issues. |

---

### 8. HO Success Rate

**Target KPI:** `HO SR% Overall`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** Mobility  
**Minimum Baseline Value:** `90%`

#### Related Features (14 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `Intra_Freq HO Prepare Failed Times` | high | 20% | 4 | Intra-Frequency HO Preparation Failure |
| 2 | `Intra_Freq HO Execution Failed Times` | high | 20% | 4 | Intra-Frequency HO Execution Failure |
| 3 | `Inter_Freq HO Prepare Failed Times` | high | 20% | 3 | Inter-Frequency HO Preparation Failure |
| 4 | `Inter_Freq HO Execution Failed Times` | high | 20% | 3 | Inter-Frequency HO Execution Failure |
| 5 | `S1 HO Execution Failed Times` | high | 20% | 3 | S1 HO Failure |
| 6 | `X2 Intra-Freq Failure` | high | 20% | 3 | X2 Intra-Frequency HO Failure |
| 7 | `X2 Inter-Freq Failure` | high | 20% | 3 | X2 Inter-Frequency HO Failure |
| 8 | `L.HHO.PingPongHo` | high | 20% | 2 | Ping-Pong HO Issue |
| 9 | `L.HHO.Prep.FailOut.NoReply` | high | 20% | 4 | HO Prep No Reply |
| 10 | `L.HHO.Prep.FailOut.PrepFailure` | high | 20% | 4 | HO Prep Failure |
| 11 | `L.HHO.Prep.FailOut.TNL` | high | 20% | 4 | HO Prep TNL Failure |
| 12 | `L.HHO.X2.Prep.FailOut.PrepFailure` | high | 20% | 3 | X2 HO Prep Failure |
| 13 | `Inter-Freq. FDD TDD HO_Failures (Prep)` | high | 20% | 3 | FDD-TDD HO Prep Failure |
| 14 | `Inter-Freq. FDD TDD HO_Failures (EXec)` | high | 20% | 3 | FDD-TDD HO Exec Failure |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `Intra_Freq HO Prepare Failed Times` | Intra-frequency HO preparation failures increased. | Check neighbor relations, target cell availability, admission control, and HO prep failure reasons. |
| `Intra_Freq HO Execution Failed Times` | Intra-frequency HO execution failures increased. | Check radio quality, A3 offset, TTT, CIO, PCI, and target cell coverage. |
| `Inter_Freq HO Prepare Failed Times` | Inter-frequency HO preparation failures increased. | Check inter-frequency neighbors, measurement configuration, frequency priority, and target availability. |
| `Inter_Freq HO Execution Failed Times` | Inter-frequency HO execution failures increased. | Check A3/A5 thresholds, TTT, CIO, target cell coverage, and PCI conflicts. |
| `S1 HO Execution Failed Times` | S1 HO execution failures increased. | Check S1 handover path, MME, transport, and target eNodeB response. |
| `X2 Intra-Freq Failure` | X2 intra-frequency HO failures increased. | Check X2 links, neighbor relation, target cell, and mobility parameters. |
| `X2 Inter-Freq Failure` | X2 inter-frequency HO failures increased. | Check X2 links, inter-frequency neighbors, and target frequency settings. |
| `L.HHO.PingPongHo` | Ping-pong handovers increased. | Tune hysteresis, TTT, CIO, A3 offset, and neighbor priorities. |
| `L.HHO.Prep.FailOut.NoReply` | HO preparation no reply failures. | Check X2/S1 connectivity and target cell. |
| `L.HHO.Prep.FailOut.PrepFailure` | HO preparation failures. | Check neighbor relations and target admission. |
| `L.HHO.Prep.FailOut.TNL` | HO preparation TNL failures. | Check transport network for HO signaling. |
| `L.HHO.X2.Prep.FailOut.PrepFailure` | X2 HO preparation failures. | Check X2 interface and neighbor relations. |
| `Inter-Freq. FDD TDD HO_Failures (Prep)` | FDD-TDD HO preparation failures. | Check FDD-TDD HO configuration. |
| `Inter-Freq. FDD TDD HO_Failures (EXec)` | FDD-TDD HO execution failures. | Check FDD-TDD HO parameters and targets. |

---

### 9. Availability

**Target KPI:** `Availability`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `1%`  
**Category:** Availability  
**Minimum Baseline Value:** `99%`

#### Related Features (4 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `(HU) Cell Unavail Time (s)` | high | 20% | 5 | Cell Unavailable Time Increase |
| 2 | `L.Cell.Unavail.Dur.Sys(s)` | high | 20% | 5 | System Unavailability |
| 3 | `L.Cell.Unavail.Dur.Manual(s)` | high | 20% | 3 | Manual Unavailability |
| 4 | `L.Cell.Unavail.Dur.Sys.S1Fail(s)` | high | 20% | 5 | S1 Failure Unavailability |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `(HU) Cell Unavail Time (s)` | Cell unavailable time increased. | Check outage, alarms, power, transmission, and site status. |
| `L.Cell.Unavail.Dur.Sys(s)` | System unavailability duration increased. | Check system faults, board alarms, transmission, and eNodeB health. |
| `L.Cell.Unavail.Dur.Manual(s)` | Manual unavailability duration increased. | Check manual lock, planned work, maintenance activity, and cell administrative state. |
| `L.Cell.Unavail.Dur.Sys.S1Fail(s)` | S1 failure unavailability duration increased. | Check S1 link, MME connection, transmission, and core network alarms. |

---

### 10. RACH Success Rate

**Target KPI:** `(HU) RACH Success Rate(%)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** Accessibility  
**Minimum Baseline Value:** `95%`

#### Related Features (5 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `RACH Setup Failed Number` | high | 20% | 4 | RACH Setup Failures |
| 2 | `RACH Contention-Based Failures` | high | 20% | 3 | Contention-Based RACH Failure |
| 3 | `RACH_att` | high | 20% | 2 | High RACH Attempts |
| 4 | `RACH Contention-Based SR` | low | 5% | 3 | Contention-Based RACH SR Drop |
| 5 | `RACH Non-Contention-Based SR` | low | 5% | 3 | Non-Contention RACH SR Drop |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `RACH Setup Failed Number` | RACH setup failures increased. | Check PRACH parameters, root sequence planning, coverage, interference, and access load. |
| `RACH Contention-Based Failures` | Contention-based RACH failures increased. | Check preamble congestion, PRACH configuration, root sequence, and access load. |
| `RACH_att` | RACH attempts increased. | Check access load, coverage, PRACH capacity, and random access configuration. |
| `RACH Contention-Based SR` | Contention-based RACH success rate decreased. | Check PRACH configuration, root sequence planning, and access congestion. |
| `RACH Non-Contention-Based SR` | Non-contention RACH success rate decreased. | Check HO-related RACH, target cell access, and PRACH settings. |

---

### 11. CSFB KPI

**Target KPI:** `CSFB SR%`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** CSFB / Voice Accessibility  
**Minimum Baseline Value:** `90%`

#### Related Features (9 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `CSFB Failure Times` | high | 20% | 4 | CSFB Failure Increase |
| 2 | `L.CSFB.PrepAtt` | high | 20% | 2 | High CSFB Preparation Attempts |
| 3 | `L.RRCRedirection.E2W.CSFB` | low | 20% | 3 | E2W CSFB Redirection Drop |
| 4 | `L.RRCRedirection.E2G.CSFB` | low | 20% | 3 | E2G CSFB Redirection Drop |
| 5 | `(TE) RRC Setup SR%` | low | 5% | 4 | LTE RRC Access Issue |
| 6 | `ERAB Setup Success Rate` | low | 5% | 3 | E-RAB Setup Issue |
| 7 | `L.FlashCSFB.E2W` | low | 20% | 2 | Flash CSFB to WCDMA |
| 8 | `Flash CSFB Ratio` | low | 20% | 2 | Flash CSFB Ratio |
| 9 | `L.RRCRedirection.E2W.Blind` | low | 20% | 2 | Blind Redirection to WCDMA |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `CSFB Failure Times` | CSFB failure times increased. | Check CSFB failure reasons, MME/S1 signaling, RRC redirection, and target 2G/3G availability. |
| `L.CSFB.PrepAtt` | CSFB preparation attempts increased, which may increase CSFB load. | Check CSFB traffic demand, MME load, S1 signaling, and whether the increase is normal voice demand. |
| `L.RRCRedirection.E2W.CSFB` | LTE-to-3G CSFB redirection count decreased compared with baseline. | Check UTRAN neighbor configuration, 3G target coverage, UTRAN frequency priority, and CSFB redirection settings. |
| `L.RRCRedirection.E2G.CSFB` | LTE-to-2G CSFB redirection count decreased compared with baseline. | Check GERAN neighbor configuration, 2G target coverage, GERAN frequency priority, LAI/TAI mapping, and CSFB redirection settings. |
| `(TE) RRC Setup SR%` | RRC setup success rate decreased, which can affect CSFB before fallback starts. | Check LTE RRC accessibility, RACH, RRC setup failures, admission control, and radio quality. |
| `ERAB Setup Success Rate` | E-RAB setup success rate decreased, indicating possible access or core signaling issue affecting services. | Check E-RAB setup failures, MME/TNL/RNL causes, admission control, radio resources, and S1 signaling. |
| `L.FlashCSFB.E2W` | Flash CSFB to WCDMA decreased. | Check flash CSFB configuration. |
| `Flash CSFB Ratio` | Flash CSFB ratio decreased. | Check flash CSFB optimization. |
| `L.RRCRedirection.E2W.Blind` | Blind redirection to WCDMA decreased. | Check blind redirection settings. |

---

### 12. VoLTE KPIs

**Target KPI:** `BA_Voice E2E VQI`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `5%`  
**Category:** VoLTE  
**Minimum Baseline Value:** `3.5`

#### Related Features (14 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `VoLTE Traffic (Erl)(Erl)` | low | 20% | 3 | VoLTE Traffic Drop |
| 2 | `L.Traffic.User.VoIP.Avg` | low | 20% | 2 | VoIP User Drop |
| 3 | `DL Traffic QCI-1` | low | 20% | 3 | QCI-1 DL Traffic Drop |
| 4 | `E-RAB Drop(ENB+MME)_Tot` | high | 20% | 5 | VoLTE Retainability Risk |
| 5 | `E-RAB Drop Rate QCI 7` | high | 20% | 4 | QCI-7 Drop Issue |
| 6 | `BA_Overall SRVCC HO Execution Success Rate (%)` | low | 5% | 4 | SRVCC Execution Degradation |
| 7 | `BA_Overall SRVCC HO Preparation Success Rate (%)` | low | 5% | 3 | SRVCC Preparation Degradation |
| 8 | `L.E-RAB.FailEst.MME.VoIP` | high | 20% | 4 | VoIP ERAB MME Failure |
| 9 | `L.E-RAB.FailEst.RNL.VoIP` | high | 20% | 4 | VoIP ERAB RNL Failure |
| 10 | `L.E-RAB.FailEst.TNL.VoIP` | high | 20% | 4 | VoIP ERAB TNL Failure |
| 11 | `L.E-RAB.FailEst.PoorCover.VoIP` | high | 20% | 4 | VoIP Poor Coverage |
| 12 | `L.E-RAB.FailEst.NoRadioRes.VoIP` | high | 20% | 4 | VoIP No Radio Resource |
| 13 | `DL user Thrpt Mbps QCI 7` | low | 20% | 3 | QCI-7 Throughput |
| 14 | `L.Traffic.ActiveUser.DL.QCI.7` | low | 20% | 2 | QCI-7 Active Users |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `VoLTE Traffic (Erl)(Erl)` | VoLTE traffic decreased. | Check VoLTE user demand, IMS service, VoLTE coverage, and QCI-1 traffic. |
| `L.Traffic.User.VoIP.Avg` | Average VoIP users decreased. | Check VoLTE traffic demand, service availability, and IMS registration behavior. |
| `DL Traffic QCI-1` | QCI-1 DL traffic decreased. | Check VoLTE bearer traffic, IMS service, and VoLTE user behavior. |
| `E-RAB Drop(ENB+MME)_Tot` | Total E-RAB drops increased. | Check VoLTE drops, radio quality, TNL/MME causes, and mobility. |
| `E-RAB Drop Rate QCI 7` | QCI-7 drop rate increased. | Check VoLTE-related bearer retainability and radio quality. |
| `BA_Overall SRVCC HO Execution Success Rate (%)` | SRVCC HO execution success rate decreased. | Check SRVCC neighbors, 2G/3G target cells, IMS/SRVCC configuration, and mobility parameters. |
| `BA_Overall SRVCC HO Preparation Success Rate (%)` | SRVCC HO preparation success rate decreased. | Check SRVCC preparation, target availability, MSC/MME coordination, and neighbor definitions. |
| `L.E-RAB.FailEst.MME.VoIP` | VoIP ERAB MME failures. | Check MME for VoIP bearers. |
| `L.E-RAB.FailEst.RNL.VoIP` | VoIP ERAB RNL failures. | Check radio network for VoIP. |
| `L.E-RAB.FailEst.TNL.VoIP` | VoIP ERAB TNL failures. | Check transport for VoIP. |
| `L.E-RAB.FailEst.PoorCover.VoIP` | VoIP poor coverage failures. | Check VoLTE coverage. |
| `L.E-RAB.FailEst.NoRadioRes.VoIP` | VoIP no radio resource failures. | Check resources for VoIP bearers. |
| `DL user Thrpt Mbps QCI 7` | QCI-7 (VoLTE) throughput degraded. | Check QCI-7 bearer quality. |
| `L.Traffic.ActiveUser.DL.QCI.7` | QCI-7 active users decreased. | Check VoLTE user demand. |

---

### 13. RRC Re-establishment

**Target KPI:** `RRC Reestablish Setup Success Rate(%)`  
**Bad Direction:** `low` (Degradation when value decreases)  
**Default Threshold:** `10%`  
**Category:** Mobility  
**Minimum Baseline Value:** `80%`

#### Related Features (8 rules)

| # | Feature | Direction | Threshold | Severity | Category |
|---|---------|-----------|-----------|----------|----------|
| 1 | `RRC Reestablish Failures(times)` | high | 20% | 4 | Re-establishment Failure |
| 2 | `L.RRC.ReEstFail.NoReply` | high | 20% | 3 | Re-establishment No Reply |
| 3 | `L.RRC.ReEstFail.Rej` | high | 20% | 3 | Re-establishment Rejection |
| 4 | `L.RRC.ReEstFail.NoCntx` | high | 20% | 3 | No Context |
| 5 | `L.RRC.ReEstFail.ResFail` | high | 20% | 3 | Resource Failure |
| 6 | `RRC Connection Drop Rate%` | high | 20% | 4 | RRC Drop Issue |
| 7 | `L.E-RAB.AbnormRel.Radio` | high | 20% | 4 | Radio Link Failure |
| 8 | `(HU) RRC Reestablish Ratio(%)` | high | 20% | 3 | High Re-establishment Ratio |

#### Detailed Reason & Recommended Actions

| Feature | Reason | Recommended Action |
|---------|--------|-------------------|
| `RRC Reestablish Failures(times)` | RRC re-establishment failures increased. | Check RLF causes, coverage, and re-establishment parameters. |
| `L.RRC.ReEstFail.NoReply` | No reply during re-establishment. | Check target cell coverage and signaling. |
| `L.RRC.ReEstFail.Rej` | Re-establishment rejected. | Check context availability and network admission. |
| `L.RRC.ReEstFail.NoCntx` | No context for re-establishment. | Check context retention and source cell. |
| `L.RRC.ReEstFail.ResFail` | Resource failure during re-establishment. | Check target cell resources. |
| `RRC Connection Drop Rate%` | RRC drops triggering re-establishment. | Check RRC drop causes. |
| `L.E-RAB.AbnormRel.Radio` | Radio failures causing RLF. | Check radio quality and coverage. |
| `(HU) RRC Reestablish Ratio(%)` | RRC re-establishment ratio increased. | Check RLF triggers and mobility. |

---

## Feature Categories Summary

### Feature Categories Used Across All KPIs

| Category | Description | Example Features |
|----------|-------------|------------------|
| **Radio Quality Issue** | Signal quality degradation | DL Average CQI, IBLER, RBLER |
| **Throughput Degradation** | Cell/User throughput issues | Cell/User DL/UL Throughput |
| **Capacity / Congestion** | Resource utilization issues | PRB Utilization, CCE AllocFail |
| **Interference Issue** | Uplink/Downlink interference | UL Interference, UpPTS Interference |
| **Availability Issue** | Cell/site availability problems | Cell Unavail Time, System Unavailability |
| **Carrier Aggregation Issue** | CA performance problems | CA Traffic Ratio, SCell Activation |
| **Extended Coverage Issue** | Coverage range problems | TA Distribution (6.6-14 km) |
| **Cell Edge Users** | Edge user performance | CEU Throughput, Border UE |
| **MIMO Efficiency** | MIMO performance issues | Reported rank 2 (%), CQI_CW0/CW1 |
| **Accessibility Issues** | Access failures | RRC Setup Failures, ERAB Setup Failures |
| **Retainability Issues** | Drop/Drop rate issues | Abnormal Releases, Drop Rate |
| **Mobility Issues** | Handover problems | HO Preparation/Execution Failures |
| **RACH Issues** | Random access problems | RACH Failures, Contention Issues |
| **CSFB Issues** | CS fallback problems | CSFB Failures, Redirection Issues |
| **VoLTE Issues** | Voice over LTE problems | VoIP ERAB Failures, QCI-1/7 Metrics |
| **SRVCC Issues** | Single Radio Voice Call Continuity | SRVCC HO Success Rate |
| **Transport Issues** | Backhaul/TNL problems | TNL Failures, S1 Failures |
| **Core Issues** | MME/Core network problems | MME Failures, MME Overload |

---

## Statistics

### Summary Table

| Metric | Count |
|--------|-------|
| **Total KPIs** | 13 |
| **Total Related Rules** | 142 |
| **Unique Features Used** | ~95 |

### KPIs by Category

| Category | KPIs |
|----------|------|
| Traffic | 2 (DL Traffic, UL Traffic) |
| Integrity | 2 (DL Throughput, UL Throughput) |
| Accessibility | 3 (RRC Setup SR, ERAB Setup SR, RACH Success Rate) |
| Retainability | 1 (Drop Rate) |
| Mobility | 2 (HO Success Rate, RRC Re-establishment) |
| Availability | 1 (Availability) |
| CSFB / Voice Accessibility | 1 (CSFB KPI) |
| VoLTE | 1 (VoLTE KPIs) |

### Rules per KPI

| KPI | Rules Count |
|-----|-------------|
| DL Traffic | 24 |
| UL Traffic | 13 |
| DL Throughput | 14 |
| UL Throughput | 8 |
| RRC Setup SR | 8 |
| ERAB Setup SR | 6 |
| Drop Rate | 15 |
| HO Success Rate | 14 |
| Availability | 4 |
| RACH Success Rate | 5 |
| CSFB KPI | 9 |
| VoLTE KPIs | 14 |
| RRC Re-establishment | 8 |
| **Total** | **142** |

---

## Appendix: Complete Column List by Category

### A. TA Distribution Columns (Coverage Analysis)
- `0-156 m`
- `156-312 m`
- `312-624 m`
- `624-1092 m`
- `1-2 km`
- `2-3.5 km`
- `3.5-6.6 km`
- `6.6-14 km`
- `TA Weighted Avg (meter)`

### B. CEU (Cell Edge User) Columns
- `(HU)CEU Cell Downlink Average Throughput`
- `(HU)CEU Cell Uplink Average Throughput`
- `(HU)CEU User Downlink Average Througput`
- `(HU)CEU User Uplink Average Throughput`
- `L.Traffic.User.BorderUE.Avg`

### C. CA (Carrier Aggregation) Columns
- `L.CA.UE.Avg`
- `L.CA.DLSCell.Act.Att`
- `L.CA.DLSCell.Add.Att`
- `L.CA.DLSCell.Add.Blind.Att`
- `L.CA.DLSCell.Add.Meas.Att`
- `MAC CA Traffic Volume GB`
- `MAC CA Traffic Ratio`
- `3CC DL PDCP CA Traffic Volume GB`
- `3CC DL PDCP CA Traffic Ratio`
- `DL PDCP FDDTDD CA Traffic Volume GB`
- `DL PDCP FDDTDD CA Traffic Ratio`

### D. MIMO/Rank Columns
- `Reported rank 2 (%)`
- `CQI_CW0`
- `CQI_CW1`

### E. RRC Re-establishment Columns
- `(HU) RRC Reestablish Ratio(%)`
- `RRC Reestablish Failures(times)`
- `RRC Reestablish Setup Success Rate(%)`
- `L.RRC.ReEst.Att`
- `L.RRC.ReEst.Succ`
- `L.RRC.ReEstFail.NoReply`
- `L.RRC.ReEstFail.Rej`
- `L.RRC.ReEstFail.NoCntx`
- `L.RRC.ReEstFail.ResFail`

### F. QCI-Specific Columns
- `DL Traffic QCI-1`
- `DL Traffic QCI-6`
- `DL Traffic QCI-7`
- `DL Traffic QCI-9`
- `DL user Thrpt Mbps QCI 7`
- `E-RAB Drop Rate QCI 7`
- `E-RAB Failures QCI 7`
- `E-RAB SR QCI 7`
- `UL Traffic GB QCI 7`
- `L.Traffic.ActiveUser.DL.QCI.7`

---

*Document Generated for LTE KPI Degradation Analyzer - Graduation Project*  
*Version 2.0 - Enhanced Configuration*
