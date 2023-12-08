import sys
from pathlib import Path

#---------------------------------------------------------#
# this is to facilitate building binaries with pyinstaller
#---------------------------------------------------------#
def getPath(relative_path):
	if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
		bundle_dir = Path(sys._MEIPASS)
	else:
		bundle_dir = Path(__file__).parent

	resource_path = f'{str(bundle_dir)}/{relative_path}'
	return resource_path