# Decision brief — Storage Conformance Pack

**To:** Raymond Gregoire, SitC Staff  
**Re:** Approve deployment of the **59-rule Storage Conformance Pack** to **&lt;ZZZ&gt;**  
**Date:** 2026-08-28  
**Source of the 59:** `aws-crud-rules-db` `JSON/storage.json`  
**Evidence lab:** account `418295699841` / `us-east-1` / harness run `ef57dcf4`  
**Detail:** `docs/management/storage-cp-validation-matrix.md`

## Decision requested

Approve **phased** deployment of the Storage CP to **&lt;ZZZ&gt;** (accounts/OUs/regions still unnamed). Do **not** treat “59 rules in the pack” as “59 rules live-proven.”

## Validation snapshot (this lab, 2026-08-28)

| Status | Count | Meaning |
|---|---:|---|
| Live-proven (NC and C cycle) | **14** | Harness toggled a resource; Config published both results |
| Partial | **1** | Snapshot public-restorable: NC only |
| Parked with cause | **2** | Engine/platform will not complete a cycle here |
| Catalog-only | **42** | In the 59; no successful harness cycle in this lab |
| **Total** | **59** | |

Live-proven identifiers: Backup min frequency/retention; EBS encrypted volumes; EFS encrypted, automatic backups, access-point user/root; S3 versioning, lifecycle, version-lifecycle, bucket-level public access, logging, public-read, public-write, ACL prohibited, SSL, default encryption KMS.

Parked:

- `fsx-openzfs-copy-tags-enabled` — FSx AVAILABLE; Config never discovered `AWS::FSx::FileSystem`.
- `s3-bucket-server-side-encryption-enabled` — modern S3 is implicitly SSE-S3; NON_COMPLIANT cannot be forced.

Partial: `ebs-snapshot-public-restorable-check` — periodic/account-scoped; COMPLIANT needs zero other public snapshots.

Related proofs **not in this 59** (do not count them as Storage CP coverage): CloudTrail log-file validation and KMS; EC2 IMDSv2, restricted SSH, `vpc-sg-port-restriction-check`. `restricted-common-ports` is also parked (`INSUFFICIENT_DATA`).

## What approval would and would not mean

**Would mean:** &lt;ZZZ&gt; may receive the pack as a *detective* control set whose parameters come from the DynamoDB catalog / `cpgNG.py` renderer, with the 14 live-proven rules treated as empirically checked in a lab.

**Would not mean:** production accounts already comply; remediation is attached; FSx/S3-SSE/snapshot-C are validated; Config in &lt;ZZZ&gt; records the same resource types as the lab.

## Conditions before deploy to &lt;ZZZ&gt;

1. Name &lt;ZZZ&gt; (account list, org units, regions).
2. Recorder in &lt;ZZZ&gt; uses an **inclusion** list for storage types (S3, EBS, EFS, Backup, FSx if in scope)—do not copy this lab’s “exclude IAM only” recorder.
3. Pack deploy is catalog-rendered YAML, not a hand-edit of the AWS sample Storage Services template (that sample is ~29 rules).
4. Exceptions process for the two parked identifiers and the snapshot COMPLIANT gap.
5. Prefer a dedicated test account for further proofs; this lab is developmental.

## Recommendation

**Conditional yes** for a pilot OU once &lt;ZZZ&gt; is specified and recorder scope is set. **No** to org-wide deploy on the claim that all 59 are live-proven.

Approver: ______________________ Date: __________
