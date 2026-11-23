import sys, runpy
MODS = r"C:\Users\Administrator\.simplexai\tools\localmodels\acbedb906f4fa14af349157f16c668b6eb50a66713d13aef76e6e049685b533d\modules"
sys.path.insert(0, MODS)
import localmodels.runtime_io as rio
orig = rio._windows_private
def spy(path, created=False):
    try:
        return orig(path, created)
    except Exception as e:
        sys.stderr.write("ACL-FAIL: %r -> %s\n" % (str(path), e))
        raise
rio._windows_private = spy
sys.argv = ["localmodels", "source", "apply", "--mode", "byok", "--runtime", "pi", "--config-stdin", "--json"]
sys.stdin = open(r"C:\Users\Administrator\byok-apply.json", "r", encoding="utf-8")
runpy.run_module("localmodels", run_name="__main__")
