"""Account-level S3 public access block toggle."""

from __future__ import annotations

from typing import Optional

import boto3

from harness.dry_run import log

ALL_ON = {
    "BlockPublicAcls": True,
    "IgnorePublicAcls": True,
    "BlockPublicPolicy": True,
    "RestrictPublicBuckets": True,
}


class AccountPabToggle:
    def __init__(self, account: str, region: Optional[str] = None):
        self.account = account
        self.region = region or "us-east-1"
        self.s3c = boto3.client("s3control", region_name=self.region)

    def get(self) -> dict:
        cfg = self.s3c.get_public_access_block(AccountId=self.account)
        return dict(cfg.get("PublicAccessBlockConfiguration") or {})

    def set(self, cfg: dict) -> dict:
        log(f"Put account PAB {cfg}")
        self.s3c.put_public_access_block(
            AccountId=self.account,
            PublicAccessBlockConfiguration=cfg,
        )
        return self.get()

    def all_on(self) -> dict:
        return self.set(dict(ALL_ON))

    def one_off(self) -> dict:
        cfg = dict(ALL_ON)
        cfg["BlockPublicAcls"] = False
        return self.set(cfg)
