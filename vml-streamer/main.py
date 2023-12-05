import time, cv2, socket, json, platform, numpy as np
import mediapipe as mp
import dearpygui.dearpygui as dpg
import dpg_callback
import process_mp_hands

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
	dpg.add_image('cv_frame', tag='webcam_image')
	# add webcam config for linux users
	if platform.system()=='Linux':
		dpg.add_text('Camera controls:')
		config_controls = ['gain', 'brightness', 'saturation']		
		for ctrl in config_controls:			
			with dpg.group(horizontal=True):
				dpg.add_text(ctrl.capitalize().ljust(15)+':')
				ctrl_val = dpg_callback.get_webcam_config(ctrl)
				dpg.add_slider_float(default_value=ctrl_val, min_value=0, max_value=ctrl_val*2, width=120, callback=dpg_callback.set_webcam_config, user_data=ctrl)
		dpg.add_spacer(height=15)
	dpg.add_button(label='Add stream', tag='add_stream', callback=dpg_callback.add_stream)
	dpg.add_group(tag='streams')

# DPG bind event handlers
dpg.bind_item_handler_registry(mainwin, window_handler)

# DPG top menu bar
with dpg.viewport_menu_bar() as mainmenu:
	with dpg.menu(label='Settings'):
		dpg.add_checkbox(tag='flip', label='Flip horizontal', default_value=True)
		dpg.add_checkbox(tag='always_on_top', label='Always on top', default_value=True, callback=dpg_callback.always_on_top)
		dpg.configure_viewport(0, always_on_top=dpg.get_value(dpg.last_item()))
		#with dpg.menu(label='Capture device:'):
		#	dpg.add_radio_button(items=list(range(10)), default_value='0', callback=change_capture_device)

# DPG show viewport
dpg.show_viewport()
dpg.set_viewport_width(frame_width+18)
dpg.set_viewport_height(720)
dpg.set_primary_window(mainwin, True)

# CV Init video capture
vcap_api = cv2.CAP_ANY
if platform.system()=='Windows': vcap_api = cv2.CAP_DSHOW
if platform.system()=='Linux':   vcap_api = cv2.CAP_V4L2
vid = cv2.VideoCapture(0, vcap_api)
display_image = None

if vid.isOpened():

	# Optionally set webcam properties
	vid.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
	vid.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
	
	# MediaPipe init
	hands = process_mp_hands.MediaPipe_Hands(frame_width, frame_height)

	# initialize static info dictionary (image width/height etc)
	info = {}
	info['image_width'] = frame_width
	info['image_height'] = frame_height

	# init calc fps
	fps_frames = 120
	fps = vid.get(cv2.CAP_PROP_FPS)
	textsize = cv2.getTextSize(f'fps: {fps}', fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.5, thickness=1)
	textpos = (5, frame_height-textsize[1]-5)
	start_time = None
	
	# "iteration" is reset at every "fps_frames", and used to calculate current fps
	# "counter" is always increasing, and used as a timestamp for the MediaPipe detector
	iteration = 0
	counter = 0

	# Main UI loop
	while dpg.is_dearpygui_running():
		iteration+=1
		counter +=1

		# read webcam frame
		success, frame = vid.read()

		if success:

			# resize to desired resolution
			#frame = cv2.resize(frame, (frame_width, frame_height))

			# flip video?
			if dpg.get_value('flip'): frame = cv2.flip(frame, 1)

			# Encode image to jpg (faster streams) and BGR -> RGB
			img_jpg = cv2.imencode('.jpg', frame, params=[cv2.IMWRITE_JPEG_QUALITY, 85])[1]
			data = cv2.imdecode(img_jpg, cv2.IMREAD_COLOR)
			data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB) # convert RGB
			display_image = data.copy()
			
			# UDP streams
			streams = dpg_callback.get_streams()
			for stream in streams:

				addr_port = (stream['address'], stream['port'])

				# INFO DICT
				if stream['type']=='Info Dictionary':
					info['streams'] = [
							{
								'type': s['type'],
								'address': s['address'],
								'port': s['port'],
							}
							for s in streams
						]
					skt.sendto(json.dumps(info).encode(), addr_port)
			
				# WEBCAM DATA
				if stream['type']=='Webcam':
					skt.sendto(img_jpg.tobytes(), addr_port)

				# MEDIAPIPE (HANDS)
				if stream['type']=='MediaPipe Hands':
					#timestamp = int(vid.get(cv2.CAP_PROP_POS_MSEC))
					timestamp = counter
					hands.apply_filter = stream['apply_filter']
					hands.one_euro_beta = stream['beta']
					hands.image = mp.Image(mp.ImageFormat.SRGB, data=data)
					hands.detect(timestamp)	
					display_image = hands.display_image
					cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
					joints_json = json.dumps(hands.joints)
					skt.sendto(joints_json.encode(), addr_port)

			# overlay fps
			if iteration==1: start_time = time.time()
			if iteration==fps_frames: 
				fps = int(fps_frames/(time.time()-start_time))
				iteration = 0
			cv2.putText(display_image, f'fps: {fps}', textpos, cv2.FONT_HERSHEY_DUPLEX, 0.5, (255,0,0), 1, cv2.LINE_AA)
			
			# DPG webcam texture update: convert to 32bit float, flatten and normalize 
			display_image = np.asfarray(display_image.ravel(), dtype='f')
			texture_data = np.true_divide(display_image, 255.0)
			dpg.set_value('cv_frame', texture_data)

		# DPG render UI
		dpg.render_dearpygui_frame()

else:
	# no webcam detected, exiting
	dpg.configure_viewport(0, width=400, height=200)
	dpg.delete_item(mainwin, children_only=True)
	dpg.delete_item(mainmenu)
	dpg.add_text('No webcam device found!', color=(255,0,0), parent=mainwin)
	dpg.add_text('Please connect a device and re-launch application.', color=(255,0,0), parent=mainwin)
	dpg.add_button(label='   OK   ', callback=dpg_callback.terminate, parent=mainwin)
	dpg.start_dearpygui()


# terminate
vid.release()
cv2.destroyAllWindows() 
dpg.destroy_context()
