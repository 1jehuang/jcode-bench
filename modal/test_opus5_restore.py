"""Offline test for the preemption checkpoint-restore logic."""
import importlib.util, pathlib, tempfile, shutil, sys, types, unittest

class _Chain:
    """Accept any chained builder call, and any decorator use."""
    def __getattr__(self, _): return lambda *a, **k: self
    def __call__(self, *a, **k):
        # Used as @app.function(...): return a decorator that passes through.
        if a and callable(a[0]) and not k:
            return a[0]
        return lambda fn: fn
sys.modules['modal'] = types.SimpleNamespace(
    is_local=lambda: False,
    App=lambda *a, **k: _Chain(),
    Volume=types.SimpleNamespace(from_name=lambda *a, **k: _Chain()),
    Secret=types.SimpleNamespace(from_local_environ=lambda *a, **k: None),
    Image=types.SimpleNamespace(from_registry=lambda *a, **k: _Chain()),
    Retries=lambda **k: None,
)
spec = importlib.util.spec_from_file_location("opus5_app", pathlib.Path("modal/opus5_app.py"))
app = importlib.util.module_from_spec(spec); spec.loader.exec_module(app)

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        self.rd, self.wd = self.root/"res", self.root/"work"
        (self.wd/"submission").mkdir(parents=True)
        (self.wd/"submission"/"solve.c").write_text("// pristine\n")
    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)
    def _ckpt(self, label, body, with_submission=True):
        base = self.rd/"checkpoints"/label
        if with_submission:
            (base/"submission").mkdir(parents=True)
            (base/"submission"/"solve.c").write_text(body)
        else:
            base.mkdir(parents=True)
        (base/"scores.jsonl").write_text('{"score": 1.5}\n')

    def test_clean_start_when_no_checkpoints(self):
        self.assertIsNone(app.restore_latest_checkpoint(self.rd, self.wd))
        self.assertIn("pristine", (self.wd/"submission"/"solve.c").read_text())

    def test_restores_newest_non_baseline_checkpoint(self):
        self._ckpt("baseline", "// baseline\n")
        self._ckpt("20260724T220000Z", "// older\n")
        self._ckpt("20260724T230000Z", "// newest\n")
        self.assertEqual(app.restore_latest_checkpoint(self.rd, self.wd), "20260724T230000Z")
        self.assertIn("newest", (self.wd/"submission"/"solve.c").read_text())
        self.assertEqual((self.wd/"scores.jsonl").read_text().strip(), '{"score": 1.5}')

    def test_never_restores_baseline_only(self):
        # Restoring the baseline would silently reset the agent's work to the
        # given implementation, which is worse than starting clean.
        self._ckpt("baseline", "// baseline\n")
        self.assertIsNone(app.restore_latest_checkpoint(self.rd, self.wd))

    def test_skips_checkpoint_without_submission(self):
        self._ckpt("20260724T230000Z", "// good\n")
        self._ckpt("20260724T235959Z", "", with_submission=False)
        self.assertEqual(app.restore_latest_checkpoint(self.rd, self.wd), "20260724T230000Z")

class FingerprintTests(unittest.TestCase):
    """Change detection must notice real edits and ignore no-ops."""

    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp())
        (self.root/"submission").mkdir()
        (self.root/"submission"/"solve.c").write_text("// given\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def test_fingerprint_changes_when_content_changes(self):
        before = app.submission_fingerprint(self.root)
        (self.root/"submission"/"solve.c").write_text("// optimized\n")
        self.assertNotEqual(before, app.submission_fingerprint(self.root))

    def test_fingerprint_stable_without_edits(self):
        self.assertEqual(
            app.submission_fingerprint(self.root), app.submission_fingerprint(self.root)
        )

    def test_fingerprint_notices_new_files(self):
        # The float-print agent added gen_tables.py alongside solve.c.
        before = app.submission_fingerprint(self.root)
        (self.root/"submission"/"gen_tables.py").write_text("print(1)\n")
        self.assertNotEqual(before, app.submission_fingerprint(self.root))

    def test_missing_submission_is_empty_not_an_error(self):
        self.assertEqual(app.submission_fingerprint(self.root/"nope"), "")


if __name__ == "__main__":
    unittest.main()
