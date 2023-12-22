import sys, subprocess
import dearpygui.dearpygui as dpg
import numpy as np
import stream_types as st
import platform

# recreates raw texture on registry
def recreate_raw_texture(width=320, height=240):
	
	with dpg.mutex():
	
		# del image
		if dpg.does_alias_exist('video_image'): 
			dpg.delete_item('video_image')
			try: dpg.remove_alias('video_image')
			except: pass

		# del texture
		if dpg.does_alias_exist('cv_frame'): 
			dpg.delete_item('cv_frame')
			try: dpg.remove_alias('cv_frame')
			except: pass

		# recreate texture
		texture_data = np.zeros(shape=(width, height, 3))
		dpg.add_raw_texture(width, height, texture_data, format=dpg.mvFormat_Float_rgb, tag='cv_frame', parent='treg')

		#recreate image
		if dpg.does_alias_exist('video_image_parent'): 
			dpg.add_image(texture_tag='cv_frame', tag='video_image', parent='video_image_parent')

# remap value between range
def change_range(unscaled, from_min, from_max, to_min, to_max):
    return (to_max-to_min)*(unscaled-from_min)/(from_max-from_min)+to_min

# resize webcam texture to match main window size
def resize_img(sender, app_data, user_data):
	img = 'webcam_image'
	win = 'mainwin'
	w, h = dpg.get_item_rect_size(win)
	newW = w-18
	newH = newW*user_data['image_aspect']
	if dpg.does_alias_exist(img):
		dpg.configure_item(img, width=newW)
		dpg.configure_item(img, height=newH)

# resize viewport to specific values
def resize_viewport(w=None, h=None):
	if w: dpg.configure_viewport(0, width=w+18)
	if h: dpg.configure_viewport(0, height=h)

# set viewport "always on top" mode
def always_on_top(sender):
	dpg.configure_viewport(0, always_on_top=dpg.get_value(sender))

# display extra settings for chosen stream type
def show_extra_settings(sender, app_data, user_data):
	for t in st.ALL:
		tag_settings_hide = f'{user_data}_{t}_settings'
		dpg.hide_item(tag_settings_hide)
	dpg.show_item(f'{user_data}_{dpg.get_value(sender)}_settings')

# rebuild stream list indices after some stream is deleted
def rebuild_indices():
	streams_grp = 'streams'
	aliases = dpg.get_aliases()
	for i, child in enumerate(dpg.get_item_children(streams_grp, 1)):
		cur_index  = str(i)
		orig_index = dpg.get_value(dpg.get_item_children(child, 1)[0])
		for old_alias in aliases:
			if old_alias.startswith(f'{orig_index}_'):
				new_alias = '_'.join(old_alias.split('_')[1:])
				new_alias = cur_index+'_'+new_alias
				item_id = dpg.get_alias_id(old_alias)
				if dpg.does_alias_exist(new_alias): dpg.remove_alias(new_alias)
				dpg.add_alias(new_alias, item_id)
				dpg.set_item_alias(item_id, new_alias)

# get all custom settings for a specific stream type and index
def get_stream_settings(tp, idx):
	aliases = dpg.get_aliases()
	settings = {}
	for alias in aliases:
		if alias.startswith(f'{idx}_{tp}_settings_'):
			settings[alias.split('_')[3]] = dpg.get_value(alias)
	return settings

# return a dictionary with all stream inputs
def get_streams():
	streams_grp = 'streams'
	streams = []
	for i, child in enumerate(dpg.get_item_children(streams_grp, 1)):
		address = dpg.get_value(f'{i}_stream_address')
		port    = dpg.get_value(f'{i}_stream_port')
		stype   = dpg.get_value(f'{i}_stream_type')

		stream = {
			'type': stype,
			'address': address,
			'port': int(port),
		}
	
		# extra settings
		stream.update(get_stream_settings(stype, i))
		
		# extra settings calculated
		if stype in [st.ST_MP_HANDS, st.ST_MP_BODY, st.ST_MP_FACE]:
			stream['beta'] = change_range(stream['smoothingFactor'], 0, 100, 100, 0.5)

		streams.append(stream)

	return streams

# get next valid stream port and index
def get_new_stream_input():
	streams_grp = 'streams'
	ports = [11110]
	stream_group = dpg.get_item_children(streams_grp, 1)
	for i, child in enumerate(stream_group):
		item = dpg.get_item_children(dpg.get_item_children(child, 1)[3], 1)[3]
		port = dpg.get_value(item)
		ports.append(int(port))
	
	ret = {
		'port': max(ports)+1,
		'index': len(stream_group),
	}
	return ret

# remove a stream
def del_stream(sender, app_data, user_data):
	global ts, ts_last, data_last	
	streams_grp = 'streams'
	index = user_data
	stream = f'{index}_stream_input'
	dpg.delete_item(stream)	
	rebuild_indices()
	ts = {}
	ts_last = {}
	data_last = {}

# add a stream
def add_stream(sender, app_data, user_data):
	# defaults
	streams_grp = 'streams'
	stream_types = st.ALL
	
	stream_input = get_new_stream_input()
	index = stream_input['index']
	port  = stream_input['port']

	with dpg.group(parent='streams', tag=f'{index}_stream_input') as grp:

		# keep track of item index
		dpg.add_input_text(default_value=index, show=False)
		
		# title
		dpg.add_spacer(height=5)
		with dpg.group(horizontal=True):
			dpg.add_button(label='X', small=True, callback=del_stream, user_data=index)
			with dpg.tooltip(dpg.last_item()):
				dpg.add_text('Delete stream')
			dpg.add_text(f'Stream:', color=(255, 102, 0))
			
		with dpg.group(horizontal=True):
			# ip address
			tag = f'{index}_stream_address'
			dpg.add_text('Address:')
			dpg.add_input_text(tag=tag, width=120)
			dpg.set_value(tag, '127.0.0.1')

			# port
			tag = f'{index}_stream_port'
			dpg.add_text('Port:')
			dpg.add_input_text(tag=tag, width=60)
			dpg.set_value(tag, str(port))

		with dpg.group(horizontal=True):
			# stream type
			tag = f'{index}_stream_type'
			dpg.add_text('Type:')
			dpg.add_combo(items=stream_types, tag=tag, width=255, callback=show_extra_settings, user_data=index)
			dpg.set_value(tag, stream_types[0])

		# extra settings per stream type
		for t in st.ALL:

			tag_settings = f'{index}_{t}_settings'

			if t in [st.ST_INFO_DICT, st.ST_VIDEO]:
				with dpg.group(tag=tag_settings, indent=20):
					dpg.add_spacer(height=1)

			elif t == st.ST_MP_HANDS:
				with dpg.group(tag=tag_settings, indent=20, show=False):
					with dpg.group(horizontal=True):
						dpg.add_text('Motion filter:'.ljust(20), color=(245, 212, 66))
						dpg.add_checkbox(tag=f'{tag_settings}_applyFilter', default_value=True)
						with dpg.tooltip(parent=dpg.last_item()): dpg.add_text('Applies a "One-Euro" smoothing filter over the input signal.', wrap=200)
						dpg.add_slider_float(tag=f'{tag_settings}_smoothingFactor', default_value=60, min_value=0, max_value=100, width=120)
					with dpg.group(horizontal=True):
						dpg.add_text('Ensure both hands:'.ljust(20), color=(245, 212, 66))
						dpg.add_checkbox(tag=f'{tag_settings}_ensureHands', default_value=False)

			elif t == st.ST_MP_BODY:
				with dpg.group(tag=tag_settings, indent=20, show=False):
					with dpg.group(horizontal=True):
						dpg.add_text('Motion filter:', color=(245, 212, 66))
						dpg.add_checkbox(tag=f'{tag_settings}_applyFilter', default_value=True)
						with dpg.tooltip(parent=dpg.last_item()): dpg.add_text('Applies a "One-Euro" smoothing filter over the input signal.', wrap=200)
						dpg.add_slider_float(tag=f'{tag_settings}_smoothingFactor', default_value=60, min_value=0, max_value=100, width=120)

			elif t == st.ST_MP_FACE:
				with dpg.group(tag=tag_settings, indent=20):
					with dpg.group(horizontal=True):
						dpg.add_text('Motion filter:', color=(245, 212, 66))
						dpg.add_checkbox(tag=f'{tag_settings}_applyFilter', default_value=True)
						with dpg.tooltip(parent=dpg.last_item()): dpg.add_text('Applies a "One-Euro" smoothing filter over the input signal.', wrap=200)
						dpg.add_slider_float(tag=f'{tag_settings}_smoothingFactor', default_value=60, min_value=0, max_value=100, width=120)
					
		dpg.add_separator()

# change specific webcam config control (linux only!) using v4l2-ctl in a subprocess
def set_webcam_custom_config(ctrl, val):
	cmd = f'v4l2-ctl --set-ctrl {ctrl}={val}'
	subprocess.call(cmd.split())

# change webcam config control (linux only!) using v4l2-ctl in a subprocess
def set_webcam_config(sender, app_data, user_data):
	ctrl = user_data
	val = dpg.get_value(sender)
	cmd = f'v4l2-ctl --set-ctrl {ctrl}={val}'
	subprocess.call(cmd.split())

# get webcam config control (linux only!) using v4l2-ctl in a subprocess
def get_webcam_config(ctrl):
	cmd = f'v4l2-ctl --get-ctrl {ctrl}'
	ret = subprocess.check_output(cmd.split()).decode()
	ret = ret.split(':')[1].replace('\n', '').strip()
	return float(ret)

