from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys


_MODULE_DIRECTORY = Path(__file__).parents[1] / "addon" / "globalPlugins" / "markdownNavigator"


def loadAddonModule(moduleName: str, fileName: str) -> ModuleType:
	spec = spec_from_file_location(moduleName, _MODULE_DIRECTORY / fileName)
	if spec is None or spec.loader is None:
		raise RuntimeError(f"Could not load {fileName}")
	module = module_from_spec(spec)
	sys.modules[moduleName] = module
	spec.loader.exec_module(module)
	return module
