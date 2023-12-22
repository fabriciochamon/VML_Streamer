import sys
from pathlib import Path
import dearpygui.dearpygui as dpg

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

# register a new icon texture
def add_icon(icon_name):
	width, height, channels, data = dpg.load_image(getPath(f'images/{icon_name}.png'))
	dpg.add_static_texture(width=width, height=height, default_value=data, tag=icon_name, parent='treg')