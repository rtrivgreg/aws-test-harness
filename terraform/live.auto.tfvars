# Matches remote state as of 2026-08-28 evening: S3 module only.
# Flipping any enable_* to true will CREATE that family, not restore old IDs.
enable_s3_test_bucket        = true
enable_ebs_test_volumes      = false
enable_efs_test_filesystems  = false
enable_cloudtrail_test       = false
enable_fsx_test              = false
enable_ec2_test              = false
enable_backup_test           = false
