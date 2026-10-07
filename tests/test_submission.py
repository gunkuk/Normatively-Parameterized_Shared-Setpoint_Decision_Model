"""Focused tests for frozen-input validation and historical recomputation."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"model"))
from npsdm import submission
import pandas as pd


class SubmissionTests(unittest.TestCase):
    def temporary_root(self):
        temp_parent = submission.ROOT/"outputs"/"test_temp"
        temp_parent.mkdir(parents=True,exist_ok=True)
        root = temp_parent / ("fixture_" + uuid.uuid4().hex)
        root.mkdir()
        def cleanup():
            if not root.resolve().is_relative_to(temp_parent.resolve()):
                raise RuntimeError("Unsafe test cleanup path")
            shutil.rmtree(root)
        self.addCleanup(cleanup)
        shutil.copytree(submission.ROOT/"data/submission",root/"data/submission")
        return root

    def test_input_hash_rejects_change(self):
        root = self.temporary_root()
        source = root/"data/submission/observations.csv"
        source.write_bytes(source.read_bytes()+b"\n")
        with patch.object(submission,"ROOT",root):
            with self.assertRaisesRegex(ValueError,"checksum changed"):
                submission.load_inputs()

    def test_reference_temperature_is_not_used_to_select_decision(self):
        root = self.temporary_root()
        source = root/"data/submission/groups.csv"
        groups = pd.read_csv(source)
        groups.loc[0,"reference_atkinson_0.0"] = 12.0
        groups.to_csv(source,index=False)
        metadata = root/"data/submission/reference.json"
        ref = json.loads(metadata.read_text())
        ref["input_sha256"]["groups.csv"] = hashlib.sha256(source.read_bytes()).hexdigest()
        metadata.write_text(json.dumps(ref),encoding="utf-8")
        with patch.object(submission,"ROOT",root):
            with self.assertRaisesRegex(ValueError,"Decision mismatch"):
                submission.run(smoke=True)

    def test_historical_groups_and_observations_are_recomputed(self):
        people,groups,_ = submission.load_inputs()
        self.assertEqual(len(people),62)
        self.assertEqual(len(groups),2400)
        self.assertEqual(float(people.loc[people.subject==14,"representative_c"].iloc[0]),23.0)


if __name__=="__main__":
    unittest.main()
