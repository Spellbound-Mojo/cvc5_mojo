"""Snapshot-derived null queries and fail-closed oracle callback contracts."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from bindgen import c_impl, config, gen_api, gen_raw


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(config.SNAPSHOT_FILE.read_text())

    def test_null_query_results_are_checked_against_generated_types(self):
        for null_result in (dict(kind="enum", type="ProofRule", name="NOT_A_RULE"),
                            dict(kind="empty-list"), dict(kind="null", type="Sort")):
            changed = copy.deepcopy(self.snap)
            changed["python"]["Proof"]["methods"]["getRule"]["null_result"] = null_result
            model = gen_api.Model(changed)
            with self.subTest(result=null_result), self.assertRaisesRegex(SystemExit, "null"):
                gen_api.emit_module(model, "Proof", model.classify()["Proof"], "fixture")

    def test_oracle_has_c_abi_and_is_separate_from_python_coverage(self):
        bound, excluded = gen_raw.classify(self.snap)
        self.assertFalse(excluded)
        function = bound["cvc5_declare_oracle_fun"]
        self.assertIn('thin abi("C") -> Ptr', function["params"][-1][1])
        self.assertNotIn("declareOracleFun", self.snap["python"]["Solver"]["methods"])
        self.assertIn("declareOracleFun", self.snap["extensions"]["Solver"])

    def test_changed_oracle_receipt_or_error_protocol_fails_closed(self):
        for key, value in (("arguments", "Cvc5Sort"), ("result", "own"),
                           ("retained_state", False), ("type_error", "abort")):
            changed = copy.deepcopy(self.snap)
            changed["callbacks"]["oracle"][key] = value
            model = gen_api.Model(changed)
            with self.subTest(key=key), self.assertRaisesRegex(SystemExit, "oracle callback"):
                gen_api.emit_module(model, "Solver", model.classify()["Solver"], "fixture")

    def test_native_oracle_result_ownership_and_error_check_are_verified(self):
        paths = ["src/api/c/cvc5_c_structs.h", "src/api/c/cvc5_c_structs.cpp",
                 "src/api/c/cvc5.cpp", "src/theory/quantifiers/oracle_checker.cpp"]
        changes = [("src/api/c/cvc5.cpp", "return fun(cterms.size(), cterms.data(), state)->d_term;",
                    "return consume(fun(cterms.size(), cterms.data(), state));"),
                   ("src/theory/quantifiers/oracle_checker.cpp", "throw LogicException(ss.str());", "abort();")]
        for filename, before, after in changes:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for rel in paths:
                    target = root / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    text = (config.SOURCE_DIR / rel).read_text()
                    if rel == filename:
                        self.assertIn(before, text)
                        text = text.replace(before, after)
                    target.write_text(text)
                with self.subTest(file=filename), self.assertRaisesRegex(SystemExit, "oracle callback"):
                    c_impl.callbacks(root)


if __name__ == "__main__":
    unittest.main()
