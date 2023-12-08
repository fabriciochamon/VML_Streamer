import sys, time, cv2, socket, json, platform, numpy as np
from webcam_stream import WebcamVideoStream
import mediapipe as mp
import dearpygui.dearpygui as dpg
import dpg_callback
import process_mp_hands, process_mp_body

# PyInstaller load splash screen
if getattr(sys, 'frozen', False): import pyi_splash

# CV VideoCapture resolution
frame_width  = 320
frame_height = 240

# Socket connection (udp)
skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# DPG init
dpg.create_context()
dpg.create_viewport(title='VML Streamer', width=frame_width, height=frame_height)
dpg.setup_dearpygui()
#dpg.show_item_registry()
#dpg.show_metrics()

# DPG register raw texture
with dpg.texture_registry():
	texture_data = np.zeros(shape=(frame_width,frame_height,3))
	dpg.add_raw_texture(frame_width, frame_height, texture_data, format=dpg.mvFormat_Float_rgb, tag='cv_frame')

# DPG event handlers
with dpg.item_handler_registry(tag='window_handler') as window_handler:
	image_aspect = frame_height/frame_width
	dpg.add_item_resize_handler(callback=dpg_callback.resize_img, user_data={'image_aspect':image_aspect})

# DPG UI
with dpg.window(tag='mainwin') as mainwin:
	
	# opencv webcam feedback
	dpg.add_image('cv_frame', tag='webcam_image')
	
	# webcam config controls (for linux only!)
	if platform.system()=='Linux':
		dpg_callback.set_webcam_custom_config('auto_exposure', 1)
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
		dpg.add_spacer(height=15)
	
	# "add stream" button
	dpg.add_button(label='Add stream', tag='add_stream', callback=dpg_callback.add_stream)
	dpg.add_group(tag='streams')

# DPG bind event handlers
dpg.bind_item_handler_registry(mainwin, window_handler)

# DPG top menu bar
with dpg.viewport_menu_bar() as mainmenu:
	with dpg.menu(label='Settings'):
		dpg.add_checkbox(tag='always_on_top', label='Always on top', default_value=True, callback=dpg_callback.always_on_top)
		dpg.add_checkbox(tag='flip', label='Flip video horizontal', default_value=True)
		dpg.configure_viewport(0, always_on_top=dpg.get_value(dpg.last_item()))
		#with dpg.menu(label='Capture device:'):
		#	dpg.add_radio_button(items=list(range(10)), default_value='0', callback=change_capture_device)

# DPG show viewport
dpg.show_viewport()
dpg.set_viewport_width(frame_width+18)
dpg.set_viewport_height(720)
dpg.set_primary_window(mainwin, True)

# CV Init video capture
vs = WebcamVideoStream(0, frame_width, frame_height).start()
display_image = None

# timestamps for mediapipe
ts={}
ts_last={}
data_last={}

# MediaPipe init
hands  = process_mp_hands.MediaPipe_Hands(frame_width, frame_height)
bodies = process_mp_body.MediaPipe_Bodies(frame_width, frame_height)

# PyInstaller close splash screen
if getattr(sys, 'frozen', False): pyi_splash.close()

if vs.isOpened():

	# Info dict init (static data: width, height, etc)
	info = {}
	info['image_width'] = frame_width
	info['image_height'] = frame_height

	# FPS calc init
	fps = 30.0
	textsize = cv2.getTextSize(f'fps: {fps}', fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.3, thickness=1)
	textpos = (5, frame_height-textsize[1]-5)
	start_time = time.time()
	counter = 0
	fps_update_rate_sec = 1 # update fps at every 1 second
	
	# DPG Main UI loop
	while dpg.is_dearpygui_running():

		# CV read webcam frame
		success, frame = vs.read()

		if success:

			# resize to desired resolution
			#frame = cv2.resize(frame, (frame_width, frame_height))

			# flip video?
			if dpg.get_value('flip'): frame = cv2.flip(frame, 1)

			# Encode image to jpg (faster streams) and BGR -> RGB
			img_jpg = cv2.imencode('.jpg', frame, params=[cv2.IMWRITE_JPEG_QUALITY, 85])[1]
			data = cv2.imdecode(img_jpg, cv2.IMREAD_COLOR)
			data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB)
			display_image = data.copy()
			
			# UDP streams
			streams = dpg_callback.get_streams()
			for i, stream in enumerate(streams):

				addr_port = (stream['address'], stream['port'])
				
				# INFO DICT
				if stream['type']=='Info Dictionary':
					info['streams'] = [
							{
								'type':    st['type'],
								'address': st['address'],
								'port':    st['port'],
							}
							for st in streams
						]
					skt.sendto(json.dumps(info).encode(), addr_port)
			
				# WEBCAM DATA
				if stream['type']=='Webcam':
					skt.sendto(img_jpg.tobytes(), addr_port)

				# MEDIAPIPE (HANDS)
				if stream['type']=='MediaPipe Hands':
					
					# init timestamp data
					if i not in ts.keys(): 
						ts[i] = 0
						ts_last[i] = -1
					
					# run detection
					ts[i] = int(vs.stream.get(cv2.CAP_PROP_POS_MSEC))
					if ts[i] > ts_last[i]: 
						ts_last[i] = ts[i]
						hands.apply_filter = stream['applyFilter']
						hands.one_euro_beta = stream['beta']
						hands.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						hands.detect(ts[i])	
					
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
				if stream['type']=='MediaPipe Body':
					
					# init timestamp data
					if i not in ts.keys(): 
						ts[i] = 0
						ts_last[i] = -1

					# run detection
					ts[i] = int(vs.stream.get(cv2.CAP_PROP_POS_MSEC))
					if ts[i] > ts_last[i]: 
						ts_last[i] = ts[i]
						bodies.apply_filter = stream['applyFilter']
						bodies.one_euro_beta = stream['beta']
						bodies.image = mp.Image(mp.ImageFormat.SRGB, data=data)
						bodies.detect(ts[i])	

					# send data
					if len(bodies.joints.keys())>0:
						display_image = bodies.display_image
						cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
						skt.sendto(json.dumps(bodies.joints).encode(), addr_port)
						data_last[i] = bodies.joints.copy()
					else:
						if i in data_last: skt.sendto(json.dumps(data_last[i]).encode(), addr_port)
			
			# Overlay FPS on webcam image
			counter+=1
			if (time.time() - start_time) > fps_update_rate_sec:
				fps = counter / (time.time() - start_time)
				counter = 0
				start_time = time.time()
			cv2.rectangle(display_image, (0, frame_height-textsize[1]-20), (105, frame_height), (50,50,50), -1)
			cv2.putText(display_image, f'MT: {fps:.1f}  CV: {vs.fps:.1f}', textpos, cv2.FONT_HERSHEY_DUPLEX, 0.3, (255,255,255), 1, cv2.LINE_AA)
			
			# DPG webcam texture update: convert to 32bit float, flatten and normalize 
			display_image = np.asfarray(display_image.ravel(), dtype='f')
			texture_data = np.true_divide(display_image, 255.0)
			dpg.set_value('cv_frame', texture_data)

		# DPG render UI (max update rate = monitor vsync)
		dpg.render_dearpygui_frame()

else:
	# no webcam detected (linux only!) 
	# on windows DSHOW will display an "empty" frame, so user needs to connect devide and restart
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
