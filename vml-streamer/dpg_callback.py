import sys, subprocess
import dearpygui.dearpygui as dpg

# closes window if no capture device found
def terminate():
	sys.exit(0)

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

# set viewport "always on top" mode
def always_on_top(sender):
	dpg.configure_viewport(0, always_on_top=dpg.get_value(sender))

# display extra settings for chosen stream type
def show_extra_settings(sender, app_data, user_data):
	dpg.hide_item(f'Info Dictionary settings {user_data}')
	dpg.hide_item(f'Webcam settings {user_data}')
	dpg.hide_item(f'MediaPipe Hands settings {user_data}')
	dpg.hide_item(f'MediaPipe Body settings {user_data}')
	dpg.show_item(f'{dpg.get_value(sender)} settings {user_data}')

# return a dictionary with all stream inputs
def get_streams():
	streams_grp = 'streams'
	streams = []
	for i, child in enumerate(dpg.get_item_children(streams_grp, 1)):
		address = dpg.get_value(dpg.get_item_children(dpg.get_item_children(child, 1)[2], 1)[1])
		port    = dpg.get_value(dpg.get_item_children(dpg.get_item_children(child, 1)[2], 1)[3])
		stype   = dpg.get_value(dpg.get_item_children(dpg.get_item_children(child, 1)[3], 1)[1])
		stream = {
			'type': stype,
			'address': address,
			'port': int(port),
		}

		#extra settings
		if stype=='MediaPipe Hands':
			stream['apply_filter'] = dpg.get_value(dpg.get_item_children(dpg.get_item_children(dpg.get_item_children(child, 1)[6], 1)[0], 1)[1])
			stream['smoothing_factor'] = dpg.get_value(dpg.get_item_children(dpg.get_item_children(dpg.get_item_children(child, 1)[6], 1)[0], 1)[3])
			stream['beta'] = change_range(stream['smoothing_factor'], 0, 100, 100, 0.5)
			stream['ensure_hand_count'] = int(dpg.get_value(dpg.get_item_children(dpg.get_item_children(dpg.get_item_children(child, 1)[6], 1)[1], 1)[1]))+1
		if stype=='MediaPipe Body':
			stream['apply_filter'] = dpg.get_value(dpg.get_item_children(dpg.get_item_children(dpg.get_item_children(child, 1)[6], 1)[0], 1)[1])
			stream['smoothing_factor'] = dpg.get_value(dpg.get_item_children(dpg.get_item_children(dpg.get_item_children(child, 1)[6], 1)[0], 1)[3])
			stream['beta'] = change_range(stream['smoothing_factor'], 0, 100, 100, 0.5)

		streams.append(stream)

	return streams

# get next valid stream port and index
def get_new_stream_input():
	streams_grp = 'streams'
	ports = [11110]
	indices = [-1]
	for i, child in enumerate(dpg.get_item_children(streams_grp, 1)):
		alias = dpg.get_item_alias(child)
		index = int(alias[6:])
		indices.append(index)
		item = dpg.get_item_children(dpg.get_item_children(child, 1)[2], 1)[3]
		port = dpg.get_value(item)
		ports.append(int(port))
	
	ret = {
		'port': max(ports)+1,
		'index': max(indices)+1,
	}
	return ret

# remove a stream
def del_stream(sender, app_data, user_data):
	global ts, ts_last, data_last
	streams_grp = 'streams'
	index = user_data
	stream = f'stream{index}'
	dpg.delete_item(stream)	
	ts = {}
	ts_last = {}
	data_last = {}

# add a stream
def add_stream(sender, app_data, user_data):
	# defaults
	streams_grp = 'streams'
	stream_types = ['Info Dictionary', 'Webcam', 'MediaPipe Hands', 'MediaPipe Body']
	
	stream_input = get_new_stream_input()
	index = stream_input['index']
	port = stream_input['port']

	with dpg.group(parent='streams', tag=f'stream{index}') as grp:
		
		# title
		dpg.add_spacer(height=5)
		with dpg.group(horizontal=True):
			dpg.add_button(label='X', small=True, callback=del_stream, user_data=index)
			with dpg.tooltip(dpg.last_item()):
				dpg.add_text('Delete stream')
			dpg.add_text(f'Stream:', color=(255, 102, 0))
			
		with dpg.group(horizontal=True):
			# ip address
			tag = f'stream_address{index}'
			dpg.add_text('Address:')
			dpg.add_input_text(tag=tag, width=120)
			dpg.set_value(tag, '127.0.0.1')

			# port
			tag = f'stream_port{index}'
			dpg.add_text('Port:')
			dpg.add_input_text(tag=tag, width=60)
			dpg.set_value(tag, str(port))

		with dpg.group(horizontal=True):
			# stream type
			tag = f'stream_type{index}'
			dpg.add_text('Type:')
			dpg.add_combo(items=stream_types, tag=tag, width=255, callback=show_extra_settings, user_data=index)
			dpg.set_value(tag, stream_types[0])

		# extra settings per stream type
		with dpg.group(tag=f'Info Dictionary settings {index}', indent=20):
			dpg.add_spacer(height=1)
		with dpg.group(tag=f'Webcam settings {index}', indent=20, show=False):
			dpg.add_spacer(height=1)
		with dpg.group(tag=f'MediaPipe Hands settings {index}', indent=20, show=False):
			with dpg.group(horizontal=True):
				dpg.add_text('Motion filter:'.ljust(20), color=(245, 212, 66))
				dpg.add_checkbox(tag=f'settings_mphands_applyfilter{index}', default_value=True)
				with dpg.tooltip(parent=dpg.last_item()):
					dpg.add_text('Applies a "One-Euro" smoothing filter over the input signal.', wrap=200)
				dpg.add_slider_float(tag=f'settings_mphands_filterbeta{index}', default_value=60, min_value=0, max_value=100, width=120)
			with dpg.group(horizontal=True):
				dpg.add_text('Ensure both hands:'.ljust(20), color=(245, 212, 66))
				dpg.add_checkbox(tag=f'settings_mphands_ensureBoth{index}', default_value=False)

		with dpg.group(tag=f'MediaPipe Body settings {index}', indent=20, show=False):
			with dpg.group(horizontal=True):
				dpg.add_text('Motion filter:', color=(245, 212, 66))
				dpg.add_checkbox(tag=f'settings_mbodies_applyfilter{index}', default_value=True)
				with dpg.tooltip(parent=dpg.last_item()):
					dpg.add_text('Applies a "One-Euro" smoothing filter over the input signal.', wrap=200)
				dpg.add_slider_float(tag=f'settings_mbodies_filterbeta{index}', default_value=60, min_value=0, max_value=100, width=120)
			
		dpg.add_separator()

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

