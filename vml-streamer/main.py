import sys, time, cv2, socket, json, platform, os, numpy as np
from video_stream import VideoStream
import mediapipe as mp
import dearpygui.dearpygui as dpg
import dearpygui_extend as dpge
import dpg_callback
import process_mp_hands, process_mp_body, process_mp_face
import stream_types as st
import resources

# PyInstaller load splash screen
if getattr(sys, 'frozen', False): import pyi_splash

# Socket connection (udp)
skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# Default image resolution
frame_width  = 320
frame_height = 240

# fixes segfault when deleting dpg textures on Linux
if platform.system()=='Linux': os.environ["__GLVND_DISALLOW_PATCHING"] = '1'

# DPG init
dpg.create_context()
dpg.create_viewport(title='VML Streamer', width=frame_width, height=frame_height)
dpg.setup_dearpygui()
dpg.add_texture_registry(tag='treg')
#dpg.show_item_registry()
#dpg.show_metrics()

# CV Init video capture
display_image = None
video_playing = True
vs = VideoStream(frame_width, frame_height).start()

# video callbacks
def video_play_pause():
	global video_playing
	video_playing = not video_playing
def video_set_frame(frameNumber):
	global vs, video_playing
	video_playing = False
	vs.frameNumber = frameNumber
	dpg.set_value('video_frame', frameNumber)

# DPG event handlers
with dpg.item_handler_registry(tag='window_handler') as window_handler:
	image_aspect = vs.height/vs.width
	dpg.add_item_resize_handler(callback=dpg_callback.resize_img, user_data={'image_aspect':image_aspect})

# DPG UI
with dpg.window(tag='mainwin') as mainwin:
	
	# opencv video feedback
	with dpg.group(tag='video_image_parent'):
		dpg.add_image(texture_tag='cv_frame', tag='video_image')
	
	# webcam config controls (for linux only!)
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
		dpg.add_image_button('icon_last_frame', width=playback_icon_size, height=playback_icon_size, callback=lambda: video_set_frame(vs.frames-1))
		dpg.add_text('fps:')
		dpg.add_input_text(tag='fps_playback', default_value='24', width=30)
		dpg.add_slider_int(tag='video_frame', min_value=0, max_value=100, width=-1, callback=lambda sender, val: vs.set_video_frame(val))
		
	dpg.add_spacer(height=15)

	# "add stream" button
	dpg.add_button(label='Add stream', tag='add_stream', callback=dpg_callback.add_stream)
	dpg.add_group(tag='streams')

# DPG bind event handlers
dpg.bind_item_handler_registry(mainwin, window_handler)

# DPG top menu bar
with dpg.viewport_menu_bar() as mainmenu:
	with dpg.menu(label='Settings'):
		with dpg.menu(label='Video source'):
			file_formats = [ {'label': 'Videos', 'formats': ['mp4', 'mov', 'mkv', 'mpg', 'mpeg', 'avi', 'wmv']} ]
			fb = dpge.add_file_browser(
				label=('Open file...', 'File browser'), 
				default_path='~',
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
				callback=lambda sender, files, cancel_pressed: vs.change_source(source_type='video', source_file=files[0]),
				)			
			with dpg.menu(label='Webcam:'):
				devices = ['None']
				devices.extend(list(range(10)))
				dpg.add_radio_button(tag='webcam_device_number', items=devices, default_value='0', callback=lambda sender, app_data: vs.change_source(source_type='webcam', source_file=int(app_data) if app_data!='None' else 11))
		dpg.add_checkbox(tag='always_on_top', label='Always on top', default_value=True, callback=dpg_callback.always_on_top)
		dpg_callback.always_on_top(dpg.last_item())
		dpg.add_checkbox(tag='flip', label='Flip video horizontal', default_value=True)			

# DPG show viewport
dpg.show_viewport()
dpg.set_viewport_width(vs.width+18)
dpg.set_viewport_height(720)
dpg.set_primary_window(mainwin, True)

# timestamps for mediapipe
ts={}
ts_last={}
data_last={}

# MediaPipe init
hands  = process_mp_hands.MediaPipe_Hands(frame_width, frame_height)
bodies = process_mp_body.MediaPipe_Bodies(frame_width, frame_height)
faces  = process_mp_face.MediaPipe_Faces(frame_width, frame_height)

# PyInstaller close splash screen
if getattr(sys, 'frozen', False): pyi_splash.close()

if vs.isOpened():

	# FPS calc init
	fps = 30.0
	textsize = cv2.getTextSize(f'fps: {fps}', fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.3, thickness=1)
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

			# resize to desired resolution
			#frame = cv2.resize(frame, (frame_width, frame_height))

			# flip?
			if dpg.get_value('flip'): frame = cv2.flip(frame, 1)

			# increment video frame
			if vs.source_type=='video' and video_playing:
				if time.time()-video_last_time>=1/float(dpg.get_value('fps_playback')):
					vs.frameNumber += 1
					vs.frameNumber = vs.frameNumber%(vs.frames-1)
					dpg.set_value('video_frame', vs.frameNumber)
					video_last_time = time.time()
			
			# Encode image to jpg (faster streams) and BGR -> RGB
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
			
				# VIDEO DATA
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
						bodies.apply_filter = stream['applyFilter']
						bodies.one_euro_beta = stream['beta']
						bodies.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						bodies.detect(ts[i])	
						counter_mpbody+=1

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
						faces.apply_filter = stream['applyFilter']
						faces.one_euro_beta = stream['beta']
						faces.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						faces.detect(ts[i])	
						counter_mpface+=1
					
					# send data
					#if len(faces.joints.keys())>=0:
					if True:
						display_image = faces.display_image
						cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
						skt.sendto(json.dumps(faces.joints).encode(), addr_port)
						data_last[i] = faces.joints.copy()
					else:
						if i in data_last: skt.sendto(json.dumps(data_last[i]).encode(), addr_port)
			
			# Overlay FPS on webcam image
			counter+=1
			if (time.time() - start_time) > fps_update_rate_sec:
				fps = counter / (time.time() - start_time)
				counter = 0
				start_time = time.time()
			cv2.rectangle(display_image, (0, vs.height-textsize[1]-20), (105, vs.height), (50,50,50), -1)
			textpos = (5, vs.height-textsize[1]-5)
			cv2.putText(display_image, f'MT: {fps:.1f}  CV: {vs.fps:.1f}', textpos, cv2.FONT_HERSHEY_DUPLEX, 0.3, (255,255,255), 1, cv2.LINE_AA)

			# DPG webcam texture update: convert to 32bit float, flatten and normalize 
			display_image = np.asfarray(display_image.ravel(), dtype='f')
			texture_data = np.true_divide(display_image, 255.0)
			dpg.set_value('cv_frame', texture_data)

		# DPG render UI (max update rate = monitor vsync)
		dpg.render_dearpygui_frame()

else:
	# no webcam detected (linux only!) 
	# on windows DSHOW will display an "empty" frame, so user needs to connect a device and restart
	dpg.configure_viewport(0, width=400, height=200)
	dpg.delete_item(mainwin, children_only=True)
	dpg.delete_item(mainmenu)
	dpg.add_text('Error: No webcam device found!', color=(255,0,0), parent=mainwin)
	dpg.add_text('Please connect a device and restart application.', color=(255,0,0), parent=mainwin)
	dpg.start_dearpygui()

# Terminate
vs.stop()
cv2.destroyAllWindows() 
dpg.destroy_context()
