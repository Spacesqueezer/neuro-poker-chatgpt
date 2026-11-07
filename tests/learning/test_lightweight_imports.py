import subprocess
import sys


def test_hud_contract_does_not_import_optional_neural_runtime():
    code = """
import sys
from importlib.abc import MetaPathFinder
class RejectTorch(MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'torch' or fullname.startswith('torch.'):
            raise AssertionError('HUD must not load PyTorch')
sys.meta_path.insert(0, RejectTorch())
from poker.hud.advisor_state import build_advisor_draft
from poker.learning import TeacherRecordImporter, LearningObservationEncoder
assert 'torch' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr


def test_generation_exports_resolve_lazily_and_keep_public_names():
    code = """
import sys
from types import ModuleType
import poker.learning as learning
assert 'poker.learning.generation' not in sys.modules
stub = ModuleType('poker.learning.generation')
names = ('DatasetGenerationConfig', 'DatasetGenerationResult', 'LearningDatasetGenerator')
for name in names:
    setattr(stub, name, object())
sys.modules[stub.__name__] = stub
for name in names:
    assert name in learning.__all__
    assert getattr(learning, name) is getattr(stub, name)
    assert getattr(learning, name) is getattr(learning, name)
try:
    learning.missing_attribute
except AttributeError:
    pass
else:
    raise AssertionError('unknown exports must raise AttributeError')
"""
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
