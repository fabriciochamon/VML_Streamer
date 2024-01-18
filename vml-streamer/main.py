import sys, time, cv2, socket, json, platform, os, numpy as np
from video_stream import VideoStream
import mediapipe as mp
import dearpygui.dearpygui as dpg
import dearpygui_extend as dpge
import dpg_callback
import process_mp_hands, process_mp_body, process_mp_face
import stream_types as st
import resources

# Defaults
video_size_at_start = 1
filebrowser_path = '~/Downloads' # user home

# PyInstaller load splash screen
if getattr(sys, 'frozen', False): import pyi_splash

# Socket connection (udp)
skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# fixes segfault when deleting DPG textures on Linux
if platform.system()=='Linux': os.environ["__GLVND_DISALLOW_PATCHING"] = '1'

# DPG init
dpg.create_context()
dpg.create_viewport(title='VML Streamer', width=320, height=240)
dpg.setup_dearpygui()
dpg.add_texture_registry(tag='treg', show=False)
#dpg.show_item_registry()
#dpg.show_metrics()

# CV Init video capture
display_image = None
video_playing = True
vs = VideoStream(size=video_size_at_start).start()

# video callbacks
def video_play_pause():
	global video_playing
	video_playing = not video_playing

def video_set_frame(frameNumber):
	global vs, video_playing
	video_playing = False
	vs.frameNumber = frameNumber
	dpg.set_value('video_frame', frameNumber)

def video_prev_next_frame(sender, app_data, user_data):
	if user_data=='prev':
		if dpg.is_key_down(dpg.mvKey_Control): vs.frameNumber = 1
		else: vs.frameNumber -=1
	else:
		if dpg.is_key_down(dpg.mvKey_Control): vs.frameNumber = vs.frames-1
		else: vs.frameNumber +=1

	dpg.set_value('video_frame', vs.frameNumber)

# DPG themes
with dpg.theme() as info_text_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_Text, (120, 120, 120))
	
# DPG event handlers
with dpg.item_handler_registry(tag='window_handler') as window_handler:
	dpg.add_item_resize_handler(callback=dpg_callback.resize_img, user_data=vs)

with dpg.handler_registry(tag='global_handler'):
    dpg.add_key_press_handler(key=dpg.mvKey_Left,  callback=video_prev_next_frame, user_data='prev')
    dpg.add_key_press_handler(key=dpg.mvKey_Right, callback=video_prev_next_frame, user_data='next')
    dpg.add_key_press_handler(key=dpg.mvKey_Up,    callback=video_play_pause)

# DPG UI
with dpg.window(tag='mainwin') as mainwin:
	
	# opencv video feedback
	with dpg.group(tag='video_image_parent'):
		dpg.add_image(texture_tag='cv_frame', tag='video_image', show=False)
		resources.add_icon('no_video')
		dpg.add_image(texture_tag='no_video', tag='video_image_empty', show=True, width=415, height=300)

	# video size mult
	with dpg.group():
		with dpg.group(horizontal=True):
			dpg.add_text('Video size: ')
			dpg.add_input_text(tag='video_size', decimal=True, on_enter=True, default_value=video_size_at_start, width=50, callback=lambda: vs.change_source(source_type=vs.source_type, source_file=vs.source_file))
			dpg.add_spacer(width=20)
			dpg.add_text('', tag='video_info_txt')
			dpg.bind_item_theme(dpg.last_item(), info_text_theme)
	
	# webcam config controls (for linux only!) - uses v4l2 driver
	if platform.system()=='Linux':
		dpg_callback.set_webcam_custom_config('auto_exposure', 1)
		with dpg.group(tag='camera_controls'):
			with dpg.collapsing_header(label='Camera controls'):
				config_controls = ['exposure_time_absolute', 'gain', 'brightness', 'saturation']
				for ctrl in config_controls:			
					with dpg.group(horizontal=True):
						dpg.add_text(ctrl.replace('_', ' ').capitalize().rjust(25)+':')
						# check if webcam device is available and set control value, ignore otherwise
						try:
							ctrl_val = dpg_callback.get_webcam_config(ctrl)
							dpg.add_slider_float(default_value=ctrl_val, min_value=0, max_value=ctrl_val*2, width=120, callback=dpg_callback.set_webcam_config, user_data=ctrl)
						except:
							pass

	# video playback controls
	playback_icon_size = 16
	resources.add_icon('icon_first_frame')
	resources.add_icon('icon_last_frame')
	resources.add_icon('icon_play_pause')
	with dpg.group(horizontal=True, tag='playback_controls', show=False):
		dpg.add_image_button('icon_first_frame', width=playback_icon_size, height=playback_icon_size, callback=lambda: video_set_frame(0))
		dpg.add_image_button('icon_play_pause', width=playback_icon_size*1.64, height=playback_icon_size, callback=video_play_pause)
		with dpg.tooltip(parent=dpg.last_item()):
			dpg.add_text('Playback controls:')
			dpg.add_text('UP arrow: play/pause', indent=5)
			dpg.add_text('LEFT arrow: previous frame', indent=5)
			dpg.add_text('RIGHT arrow: next frame', indent=5)
			dpg.add_text('CTRL+LEFT arrow: goto first frame', indent=5)
			dpg.add_text('CTRL+RIGHT arrow: goto last frame', indent=5)
		dpg.add_image_button('icon_last_frame', width=playback_icon_size, height=playback_icon_size, callback=lambda: video_set_frame(vs.frames-1))
		dpg.add_text('fps:')
		dpg.add_input_text(tag='fps_playback', default_value='24', width=30)
		dpg.add_slider_int(tag='video_frame', min_value=0, max_value=100, width=-1, callback=lambda sender, val: video_set_frame(val))



	dpg.add_spacer(height=15)

	# "add stream" button
	dpg.add_button(label='Add stream', tag='add_stream', callback=dpg_callback.add_stream)
	dpg.add_group(tag='streams')

# DPG bind window event handler
dpg.bind_item_handler_registry(mainwin, window_handler)

# DPG top menu bar
with dpg.viewport_menu_bar() as mainmenu:
	with dpg.menu(label='Settings'):
		with dpg.menu(label='Video source'):

			# file browser
			file_formats = [ {'label': 'Videos', 'formats': ['mp4', 'mov', 'mkv', 'mpg', 'mpeg', 'avi', 'wmv', 'webm']} ]
			fb = dpge.add_file_browser(
				label=('Open file...', 'File browser'), 
				default_path=filebrowser_path,
				width=750, 
				height=610,
				pos=[10,30],
				path_input_style=dpge.file_browser.PATH_INPUT_STYLE_TEXT_ONLY,
				show_as_window=True, 
				show_ok_cancel=True, 
				filetype_filter=file_formats, 				
				collapse_sequences=True,
				collapse_sequences_checkbox=False,
				icon_size=0.7,
				allow_multi_selection=False,
				allow_create_new_folder=False,
				show_nav_icons=False,
				callback=lambda sender, files, cancel_pressed: vs.load_video_file(files, cancel_pressed),
				)	

			button = dpg.get_item_children(mainmenu, 1)[0]
			button = dpg.get_item_children(button, 1)[0]
			button = dpg.get_item_children(button, 1)[0]
			dpg.configure_item(button, callback=lambda: dpg_callback.show_filebrowser(fb))

			# webcam devices
			if getattr(sys, 'frozen', False): pyi_splash.update_text('Fetching available webcam devices...')
			with dpg.menu(label='Webcam:'):
				devices = ['None']
				devices.extend(dpg_callback.get_connected_devices())
				dpg.add_radio_button(tag='webcam_device_number', items=devices, default_value='None', callback=lambda sender, app_data: vs.change_source(source_type='webcam', source_file=app_data))

		with dpg.menu(label='Video capture API'):
			cap_api_items = ['First available']
			cap_api_default = 'First available'
			if platform.system()=='Windows': cap_api_items.extend(['Direct Show'])
			if platform.system()=='Linux': cap_api_items.extend(['V4L2'])
			dpg.add_radio_button(tag='cv_vid_cap_api', items=cap_api_items, default_value=cap_api_default)

		# always on top		
		dpg.add_checkbox(tag='always_on_top', label='Always on top', default_value=True, callback=dpg_callback.always_on_top)
		dpg_callback.always_on_top(dpg.last_item())

		# flip video
		dpg.add_checkbox(tag='flip', label='Flip video horizontal', default_value=True)			

# DPG show viewport
dpg.show_viewport()
dpg.set_viewport_width(450)
dpg.set_viewport_height(720)
dpg.set_primary_window(mainwin, True)

# timestamps for mediapipe
ts={}
ts_last={}
data_last={}

# MediaPipe init
hands  = process_mp_hands.MediaPipe_Hands(vs.width, vs.height)
bodies = process_mp_body.MediaPipe_Bodies(vs.width, vs.height)
faces  = process_mp_face.MediaPipe_Faces(vs.width, vs.height)

# PyInstaller close splash screen
if getattr(sys, 'frozen', False): pyi_splash.close()

if vs.isOpened():

	# FPS calc init (main thread)
	fps = 30.0
	start_time = time.time()
	counter = 0
	fps_update_rate_sec = 1 # update fps at every 1 second

	# per stream counters (used as timestamp data for mediapipe)
	counter_mphands  = 0
	counter_mpbody   = 0
	counter_mpface   = 0

	# video playback time
	video_last_time = time.time()

	# DPG Main UI loop
	while dpg.is_dearpygui_running():

		# CV read frame
		success, frame = vs.read()

		if success:

			# flip image?
			if dpg.get_value('flip'): frame = cv2.flip(frame, 1)

			# if playing video, increment frame
			if vs.source_type=='video' and video_playing:
				fps_pb = dpg.get_value('fps_playback')
				if fps_pb.strip()=='': fps_pb = 30
				if time.time()-video_last_time>=1/(float(fps_pb)*1.666):
					vs.set_counter = True
					vs.frameNumber += 1  # increment
					vs.frameNumber = vs.frameNumber%(vs.frames-1)  # loop
					dpg.set_value('video_frame', vs.frameNumber)
					video_last_time = time.time()
			
			# Encode image to jpg (faster streams) and convert BGR -> RGB
			img_jpg = cv2.imencode('.jpg', frame, params=[cv2.IMWRITE_JPEG_QUALITY, 85])[1]
			data = cv2.imdecode(img_jpg, cv2.IMREAD_COLOR)
			data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
			display_image = data.copy()
		
			
			# loop through streams
			streams = dpg_callback.get_streams()
			for i, stream in enumerate(streams):

				addr_port = (stream['address'], stream['port'])
				
				# INFO DICT
				if stream['type'] == st.ST_INFO_DICT:
					info = {}
					info['image_width']  = vs.width
					info['image_height'] = vs.height
					info['source_type']  = vs.source_type
					info['source_file']  = vs.source_file
					if vs.source_type=='video':
						info['num_frames']  = vs.frames
						info['curr_frame']  = vs.frameNumber
						info['source_fps']  = vs.source_fps
					info['streams'] = [
							{
								'type':    st['type'],
								'address': st['address'],
								'port':    st['port'],
							}
							for st in streams
						]
					skt.sendto(json.dumps(info).encode(), addr_port)
			
				# VIDEO
				if stream['type'] == st.ST_VIDEO:
					skt.sendto(img_jpg.tobytes(), addr_port)

				# MEDIAPIPE (HANDS)
				if stream['type'] == st.ST_MP_HANDS:

					# init timestamp data
					if i not in ts.keys(): 
						ts[i] = 0
						ts_last[i] = -1
					
					# run detection
					ts[i] = counter_mphands
					if ts[i] > ts_last[i]: 
						ts_last[i] = ts[i]
						hands.apply_filter = stream['applyFilter']
						hands.one_euro_beta = stream['beta']
						hands.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						hands.detect(ts[i])	
						counter_mphands+=1
					
					# send data
					ensure_hand_count = int(stream['ensureHands'])+1 if 'ensureHands' in stream.keys() else 1
					if len(hands.joints.keys())>=ensure_hand_count:
						display_image = hands.display_image
						cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
						skt.sendto(json.dumps(hands.joints).encode(), addr_port)
						data_last[i] = hands.joints.copy()
					else:
						if i in data_last: skt.sendto(json.dumps(data_last[i]).encode(), addr_port)
					
				# MEDIAPIPE (BODY)
				if stream['type'] == st.ST_MP_BODY:
					
					# init timestamp data
					if i not in ts.keys(): 
						ts[i] = 0
						ts_last[i] = -1

					# run detection
					ts[i] = counter_mpbody
					if ts[i] > ts_last[i]: 
						ts_last[i] = ts[i]
						bodies.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						bodies.detect(ts[i])	
						counter_mpbody+=100

					# send data
					if len(bodies.joints.keys())>0:
						display_image = bodies.display_image
						cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
						skt.sendto(json.dumps(bodies.joints).encode(), addr_port)
						data_last[i] = bodies.joints.copy()
					else:
						if i in data_last: skt.sendto(json.dumps(data_last[i]).encode(), addr_port)

				# MEDIAPIPE (FACE)
				if stream['type'] == st.ST_MP_FACE:
					
					# init timestamp data
					if i not in ts.keys(): 
						ts[i] = 0
						ts_last[i] = -1
					
					# run detection
					ts[i] = counter_mpface
					if ts[i] > ts_last[i]: 
						ts_last[i] = ts[i]
						faces.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						faces.detect(ts[i])	
						counter_mpface+=100
					
					# send data
					display_image = faces.display_image
					cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
					skt.sendto(json.dumps(faces.joints).encode(), addr_port)
					data_last[i] = faces.joints.copy()

			
			# Overlay FPS
			# MT = main thread
			# CV = openCV video thread
			counter+=1
			if (time.time() - start_time) > fps_update_rate_sec:
				fps = counter / (time.time() - start_time)
				counter = 0
				start_time = time.time()
			dpg.set_value('video_info_txt', f'{vs.fps:.1f} fps @ {vs.width}x{vs.height}')
			
			# DPG webcam texture update: convert to 32bit float, flatten and normalize 
			display_image = np.asfarray(display_image.ravel(), dtype='f')
			texture_data = np.true_divide(display_image, 255.0)
	
			if dpg.does_alias_exist('cv_frame'):
				with dpg.mutex(): dpg.set_value('cv_frame', texture_data)			
			
		# DPG render UI (max update rate = monitor vsync)
		dpg.render_dearpygui_frame()

# Terminate
vs.stop()
cv2.destroyAllWindows() 
dpg.destroy_context()
