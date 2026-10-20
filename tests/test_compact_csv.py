import csv
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline" / "bronze"))
import compact_csv

class FakeR2:
    def __init__(self):
        self.items={}
    def head_object(self, Bucket, Key):
        if Key not in self.items:
            raise ClientError({"Error":{"Code":"404", "Message":"missing"}},"HeadObject")
        d,m=self.items[Key]
        return {"ContentLength":len(d),"Metadata":m}
    def download_file(self, bucket, key, path):
        Path(path).write_bytes(self.items[key][0])
    def upload_file(self, path, bucket, key, ExtraArgs=None):
        self.items[key]=(Path(path).read_bytes(), ExtraArgs.get("Metadata",{}) if ExtraArgs else {})
    def put_object(self, Bucket, Key, Body, **kwargs):
        self.items[Key]=(Body,{})
    def list_objects_v2(self, Bucket, Prefix, MaxKeys, **kwargs):
        return {"Contents":[{"Key":k} for k in sorted(self.items) if k.startswith(Prefix)], "IsTruncated":False}
    def delete_object(self, Bucket, Key):
        self.items.pop(Key,None)

def create_csv(path, contents):
    with open(path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["dav_row_id","dav_price_vnd"])
        w.writeheader()
        w.writerows(contents)

class CompactCsvTest(unittest.TestCase):
    def test_append_only_dedup_and_change(self):
        fake=FakeR2()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"in.csv"
            create_csv(p,[{"dav_row_id":"A","dav_price_vnd":"100"},{"dav_row_id":"B","dav_price_vnd":"200"}])
            a=compact_csv.merge_snapshot(fake,"dav",p,minimum=1)
            self.assertEqual(a["new_events"],2)
            b=compact_csv.merge_snapshot(fake,"dav",p,minimum=1)
            self.assertEqual(b["new_events"],0)
            create_csv(p,[{"dav_row_id":"A","dav_price_vnd":"110"},{"dav_row_id":"B","dav_price_vnd":"200"},{"dav_row_id":"C","dav_price_vnd":"300"}])
            c=compact_csv.merge_snapshot(fake,"dav",p,minimum=1)
            self.assertEqual(c["new_events"],2)
            rows=list(csv.DictReader(io.StringIO(fake.items["bronze/dav.csv"][0].decode())))
            self.assertEqual(len(rows),4)
            self.assertEqual([x["__operation"] for x in rows],["INSERT","INSERT","UPDATE","INSERT"])
    def test_refuse_deletion_without_replacement(self):
        s=FakeR2()
        s.items["bronze/icd10/old.gz"]=(b"old",{})
        with self.assertRaises(RuntimeError):
            compact_csv.cleanup_legacy_bronze(s,dry_run=False)
        self.assertIn("bronze/icd10/old.gz",s.items)
        s.items["bronze/icd10.csv"]=(b"header\n",{})
        compact_csv.cleanup_legacy_bronze(s,dry_run=False)
        self.assertNotIn("bronze/icd10/old.gz",s.items)
        self.assertIn("bronze/icd10.csv",s.items)
    def test_never_replace_valid_history_with_empty_snapshot(self):
        s=FakeR2()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"test.csv"
            create_csv(p,[{"dav_row_id":"A","dav_price_vnd":"100"}])
            compact_csv.merge_snapshot(s,"dav",p)
            prior=s.items["bronze/dav.csv"][0]
            create_csv(p,[])
            with self.assertRaises(ValueError):
                compact_csv.merge_snapshot(s,"dav",p)
            self.assertEqual(prior,s.items["bronze/dav.csv"][0])

if __name__=="__main__":
    unittest.main()
