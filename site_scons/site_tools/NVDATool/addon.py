import zipfile
from collections.abc import Iterable
from pathlib import Path


def createAddonBundleFromPath(path: str | Path, dest: str, excludePatterns: Iterable[str]):
	"""Creates a bundle from a directory that contains an addon manifest file."""
	if isinstance(path, str):
		path = Path(path)
	basedir = path.absolute()
	with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
		for p in basedir.rglob("*"):
			if p.is_dir():
				continue
			pathInBundle = p.relative_to(basedir)
			if not any(pathInBundle.match(pattern) for pattern in excludePatterns):
				z.write(p, pathInBundle)
	return dest
