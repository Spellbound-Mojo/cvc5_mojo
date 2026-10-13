"""Focused extraction, ownership and translation regressions for plugins."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from bindgen import c_headers, c_impl, config, gen_api, gen_raw, translate


class PluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snap = json.loads(config.SNAPSHOT_FILE.read_text())

    def test_callback_signatures_and_layout_match_pinned_headers(self):
        native = c_headers.types()["Cvc5Plugin"]
        self.assertEqual(native, self.snap["c_types"]["Cvc5Plugin"])
        fields = {f["name"]: f for f in native["fields"]}
        check = gen_raw.callback_type(fields["check"], self.snap["c_types"])
        self.assertIn('thin abi("C")', check)
        self.assertIn("Pointer[UInt, MutUntrackedOrigin]", check)
        bound, excluded = gen_raw.classify(self.snap)
        self.assertIn("cvc5_add_plugin", bound)
        self.assertNotIn("cvc5_add_plugin", excluded)
        self.assertIn("cvc5_declare_oracle_fun", bound)
        self.assertEqual(excluded, {})

    def test_changed_callback_export_or_state_fails_closed(self):
        for key, value in (("exports", []), ("state", None), ("field", "missing")):
            snap = copy.deepcopy(self.snap)
            snap["callbacks"]["methods"]["notifySatClause"][key] = value
            model = gen_api.Model(snap)
            with self.subTest(key=key), self.assertRaisesRegex(SystemExit, "callback"):
                gen_api.emit_module(model, "Plugin", model.classify()["Plugin"], snap["cvc5"]["version"])

    def test_changed_native_table_retention_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for filename in ("cvc5_c_structs.h", "cvc5_c_structs.cpp", "cvc5.cpp"):
                path = Path("src/api/c") / filename
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (config.SOURCE_DIR / path).read_text()
                if filename.endswith(".h"):
                    text = text.replace("Cvc5Plugin* d_plugin;", "Cvc5Plugin d_plugin;")
                target.write_text(text)
            with self.assertRaisesRegex(SystemExit, "table retention changed"):
                c_impl.callbacks(root)

    def test_commands_retain_callback_storage_via_existing_anchor(self):
        model, table = gen_api.generated(self.snap)
        self.assertEqual(model.anchors["Command"], "InputParser")
        command = gen_api.emit_module(model, "Command", table["Command"], "fixture")
        self.assertIn("var _anchor: Optional[ArcPointer[_InputParserState]]", command)
        self.assertIn("with _CallbackCall(solver._o[].callbacks)", command)
        parser = gen_api.emit_module(model, "InputParser", table["InputParser"], "fixture")
        self.assertIn("self._o[].callbacks = solver._o[].callbacks", parser)
        self.assertIn("with _CallbackCall(self._o[].callbacks)", parser)

    def test_both_upstream_plugin_classes_translate_independently(self):
        api = translate.Api(self.snap)
        source = config.SOURCE_DIR / "test/unit/api/python/test_solver.py"
        for name, cls in (("test_plugin_unsat", "PluginUnsat"), ("test_plugin_listen", "PluginListen")):
            result = translate.translate_file(source, api, only=name)
            with self.subTest(name=name):
                self.assertEqual(result["run"], [name])
                self.assertEqual(result["not_translated"], {})
                self.assertIn(f"struct {cls}(Plugin):", result["text"])
                self.assertIn(f"ArcPointer({cls}(tm))", result["text"])
                self.assertIn("Term", result["text"].split("from cvc5_mojo import ")[1].splitlines()[0])
                if name == "test_plugin_unsat":
                    self.assertIn("return lemmas.copy()", result["text"])
        self.assertEqual(api.plugins, {}, "local classes must not leak into later modules")

    def test_dynamic_names_are_explicitly_untranslated(self):
        source = '''
class Dynamic(Plugin):
    def __init__(self, tm):
        super().__init__(tm)
        self.name = "dynamic"
    def getName(self):
        return self.name
def test_dynamic():
    p = Dynamic(TermManager())
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test_fixture.py"
            path.write_text(source)
            result = translate.translate_file(path, translate.Api(self.snap))
        self.assertIn("constant string", result["not_translated"]["test_dynamic"])
        self.assertEqual(result["run"], [])
