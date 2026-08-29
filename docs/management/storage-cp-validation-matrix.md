# Storage CP — 59-row validation matrix

Pack source: `rtrivgreg/aws-crud-rules-db` `JSON/storage.json` (59 names).  
Lab: `418295699841` `us-east-1` run `ef57dcf4` as of 2026-08-29 13:50 EDT.  
Statuses: **live** = NC+C cycle; **partial** = NC only; **parked** = attempted, will not complete here; **catalog-only** = in the 59, no live cycle in this lab.

**Counts:** live **34** · partial 1 · parked 6 · catalog-only **18** · total 59.

| # | Rule name | Identifier (typical) | Family | Status | Note |
|--:|---|---|---|---|---|
| 1 | backup-plan-min-frequency-and-min-retention-check | BACKUP_PLAN_MIN_FREQUENCY_AND_MIN_RETENTION_CHECK | Backup | live | |
| 2 | backup-recovery-point-encrypted | BACKUP_RECOVERY_POINT_ENCRYPTED | Backup | parked | 2026-08-29 EBS jobs COMPLETED; Config RecoveryPoint = [] |
| 3 | backup-recovery-point-manual-deletion-disabled | BACKUP_RECOVERY_POINT_MANUAL_DELETION_DISABLED | Backup | catalog-only | Same RP type as parked row 2 |
| 4 | backup-recovery-point-minimum-retention-check | BACKUP_RECOVERY_POINT_MINIMUM_RETENTION_CHECK | Backup | catalog-only | Same RP type as parked row 2 |
| 5 | cloudtrail-all-read-s3-data-event-check | CLOUDTRAIL_ALL_READ_S3_DATA_EVENT_CHECK | S3/CT | live | 2026-08-29 |
| 6 | cloudtrail-all-write-s3-data-event-check | CLOUDTRAIL_ALL_WRITE_S3_DATA_EVENT_CHECK | S3/CT | live | 2026-08-29 |
| 7 | ebs-in-backup-plan | EBS_IN_BACKUP_PLAN | EBS | catalog-only | Coverage family; do not rerun this recorder |
| 8 | ebs-last-backup-recovery-point-created | EBS_LAST_BACKUP_RECOVERY_POINT_CREATED | EBS | catalog-only | |
| 9 | ebs-meets-restore-time-target | EBS_MEETS_RESTORE_TIME_TARGET | EBS | catalog-only | |
| 10 | ebs-optimized-instance | EBS_OPTIMIZED_INSTANCE | EBS | live | 2026-08-29 210s; c3.xlarge EbsOptimized=false NC; t3.nano C |
| 11 | ebs-resources-in-logically-air-gapped-vault | EBS_RESOURCES_IN_LOGICALLY_AIR_GAPPED_VAULT | EBS | catalog-only | |
| 12 | ebs-resources-protected-by-backup-plan | EBS_RESOURCES_PROTECTED_BY_BACKUP_PLAN | EBS | parked | 2026-08-29 INSUFFICIENT_DATA, EvaluationResults [] |
| 13 | ebs-snapshot-block-public-access | EBS_SNAPSHOT_BLOCK_PUBLIC_ACCESS | EBS | parked | Stale CI |
| 14 | ebs-snapshot-public-restorable-check | EBS_SNAPSHOT_PUBLIC_RESTORABLE_CHECK | EBS | partial | NC proven; C account-scoped |
| 15 | ec2-ebs-encryption-by-default | EC2_EBS_ENCRYPTION_BY_DEFAULT | EBS | live | 2026-08-29; left enabled |
| 16 | ec2-launch-templates-ebs-volume-encrypted | EC2_LAUNCH_TEMPLATES_EBS_VOLUME_ENCRYPTED | EBS | live | 2026-08-29 LT default version Encrypted false/true; 275s |
| 17 | ec2-spot-fleet-request-ct-encryption-at-rest | EC2_SPOT_FLEET_REQUEST_CT_ENCRYPTION_AT_REST | EBS | catalog-only | |
| 18 | efs-access-point-enforce-root-directory | EFS_ACCESS_POINT_ENFORCE_ROOT_DIRECTORY | EFS | live | |
| 19 | efs-access-point-enforce-user-identity | EFS_ACCESS_POINT_ENFORCE_USER_IDENTITY | EFS | live | |
| 20 | efs-automatic-backups-enabled | EFS_AUTOMATIC_BACKUPS_ENABLED | EFS | live | |
| 21 | efs-encrypted-check | EFS_ENCRYPTED_CHECK | EFS | live | |
| 22 | efs-filesystem-ct-encrypted | EFS_FILESYSTEM_CT_ENCRYPTED | EFS | live | 2026-08-29 |
| 23 | efs-in-backup-plan | EFS_IN_BACKUP_PLAN | EFS | catalog-only | Coverage family; do not rerun this recorder |
| 24 | efs-mount-target-public-accessible | EFS_MOUNT_TARGET_PUBLIC_ACCESSIBLE | EFS | live | 2026-08-29 167s; public MT NC / private MT C; throwaway /28 cleaned |
| 25 | efs-resources-protected-by-backup-plan | EFS_RESOURCES_PROTECTED_BY_BACKUP_PLAN | EFS | catalog-only | Coverage family; do not rerun this recorder |
| 26 | encrypted-volumes | ENCRYPTED_VOLUMES | EBS | live | |
| 27 | fsx-lustre-copy-tags-to-backups | FSX_LUSTRE_COPY_TAGS_TO_BACKUPS | FSx | catalog-only | |
| 28 | fsx-ontap-deployment-type-check | FSX_ONTAP_DEPLOYMENT_TYPE_CHECK | FSx | catalog-only | |
| 29 | fsx-openzfs-copy-tags-enabled | FSX_OPENZFS_COPY_TAGS_ENABLED | FSx | parked | Config never discovered FS |
| 30 | fsx-resources-protected-by-backup-plan | FSX_RESOURCES_PROTECTED_BY_BACKUP_PLAN | FSx | catalog-only | |
| 31 | fsx-windows-deployment-type-check | FSX_WINDOWS_DEPLOYMENT_TYPE_CHECK | FSx | catalog-only | |
| 32 | s3-access-point-in-vpc-only | S3_ACCESS_POINT_IN_VPC_ONLY | S3 | live | |
| 33 | s3-access-point-public-access-blocks | S3_ACCESS_POINT_PUBLIC_ACCESS_BLOCKS | S3 | live | |
| 34 | s3-account-level-public-access-blocks-periodic | S3_ACCOUNT_LEVEL_PUBLIC_ACCESS_BLOCKS_PERIODIC | S3 | live | 2026-08-29 147s; PAB all-true restored |
| 35 | s3-bucket-acl-prohibited | S3_BUCKET_ACL_PROHIBITED | S3 | live | |
| 36 | s3-bucket-blacklisted-actions-prohibited | S3_BUCKET_BLACKLISTED_ACTIONS_PROHIBITED | S3 | live | |
| 37 | s3-bucket-cross-region-replication-enabled | S3_BUCKET_CROSS_REGION_REPLICATION_ENABLED | S3 | live | |
| 38 | s3-bucket-default-lock-enabled | S3_BUCKET_DEFAULT_LOCK_ENABLED | S3 | live | |
| 39 | s3-bucket-level-public-access-prohibited | S3_BUCKET_LEVEL_PUBLIC_ACCESS_PROHIBITED | S3 | live | |
| 40 | s3-bucket-logging-enabled | S3_BUCKET_LOGGING_ENABLED | S3 | live | |
| 41 | s3-bucket-mfa-delete-enabled | S3_BUCKET_MFA_DELETE_ENABLED | S3 | catalog-only | Needs root MFA |
| 42 | s3-bucket-policy-grantee-check | S3_BUCKET_POLICY_GRANTEE_CHECK | S3 | live | |
| 43 | s3-bucket-policy-not-more-permissive | S3_BUCKET_POLICY_NOT_MORE_PERMISSIVE | S3 | live | |
| 44 | s3-bucket-public-read-prohibited | S3_BUCKET_PUBLIC_READ_PROHIBITED | S3 | live | |
| 45 | s3-bucket-public-write-prohibited | S3_BUCKET_PUBLIC_WRITE_PROHIBITED | S3 | live | |
| 46 | s3-bucket-replication-enabled | S3_BUCKET_REPLICATION_ENABLED | S3 | live | |
| 47 | s3-bucket-server-side-encryption-enabled | S3_BUCKET_SERVER_SIDE_ENCRYPTION_ENABLED | S3 | parked | Implicit SSE-S3 |
| 48 | s3-bucket-ssl-requests-only | S3_BUCKET_SSL_REQUESTS_ONLY | S3 | live | |
| 49 | s3-bucket-tagged | S3_BUCKET_TAGGED | S3 | live | |
| 50 | s3-bucket-versioning-enabled | S3_BUCKET_VERSIONING_ENABLED | S3 | live | |
| 51 | s3-default-encryption-kms | S3_DEFAULT_ENCRYPTION_KMS | S3 | live | |
| 52 | s3-event-notifications-enabled | S3_EVENT_NOTIFICATIONS_ENABLED | S3 | live | |
| 53 | s3express-dir-bucket-lifecycle-rules-check | S3EXPRESS_DIR_BUCKET_LIFECYCLE_RULES_CHECK | S3 | catalog-only | |
| 54 | s3-last-backup-recovery-point-created | S3_LAST_BACKUP_RECOVERY_POINT_CREATED | S3 | catalog-only | |
| 55 | s3-lifecycle-policy-check | S3_LIFECYCLE_POLICY_CHECK | S3 | live | |
| 56 | s3-meets-restore-time-target | S3_MEETS_RESTORE_TIME_TARGET | S3 | catalog-only | |
| 57 | s3-resources-in-logically-air-gapped-vault | S3_RESOURCES_IN_LOGICALLY_AIR_GAPPED_VAULT | S3 | catalog-only | |
| 58 | s3-resources-protected-by-backup-plan | S3_RESOURCES_PROTECTED_BY_BACKUP_PLAN | S3 | catalog-only | Coverage family; do not rerun this recorder |
| 59 | s3-version-lifecycle-policy-check | S3_VERSION_LIFECYCLE_POLICY_CHECK | S3 | live | |
