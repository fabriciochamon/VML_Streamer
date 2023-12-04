import cv2, socket, json, platform, numpy as np
import mediapipe as mp
import dearpygui.dearpygui as dpg
import dpg_callback
import process_mp_hands

# Socket connection (udp)
skt = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

# DPG init
dpg.create_context()
dpg.create_viewport(title='VML Streamer', width=400, height=400)
dpg.setup_dearpygui()
#dpg.show_item_registry()

# CV Video Capture resolution
frame_width  = 320
frame_height = 240

# DPG init webcam raw texture
image_aspect = frame_height/frame_width
with dpg.texture_registry():
	texture_data = np.zeros(shape=(frame_width,frame_height,3))
	dpg.add_raw_texture(frame_width, frame_height, texture_data, format=dpg.mvFormat_Float_rgb, tag='cv_frame')

# DPG event handlers
with dpg.item_handler_registry(tag='window_handler') as window_handler:
	dpg.add_item_resize_handler(callback=dpg_callback.resize_img, user_data={'image_aspect':image_aspect})

# DPG UI
with dpg.window(tag='mainwin') as mainwin:
	dpg.add_image('cv_frame', tag='webcam_image')
	dpg.add_button(label='Add stream', tag='add_stream', callback=dpg_callback.add_stream)
	dpg.add_group(tag='streams')

# DPG bind event handlers
dpg.bind_item_handler_registry(mainwin, window_handler)

# DPG top menu bar
with dpg.viewport_menu_bar() as mainmenu:
	with dpg.menu(label='Settings'):
		#with dpg.menu(label='Capture device:'):
		#	dpg.add_radio_button(items=list(range(10)), default_value='0', callback=change_capture_device)
		dpg.add_checkbox(tag='flip', label='Flip horizontal', default_value=True)

# DPG show viewport
dpg.show_viewport()
dpg.set_viewport_width(frame_width+18)
dpg.set_viewport_height(frame_height*3)
dpg.set_primary_window(mainwin, True)

# CV Init video capture
webcam_found = False
if platform.system()=='Windows':
	vid = cv2.VideoCapture(0, cv2.CAP_DSHOW)
	webcam_found = vid.isOpened()
elif platform.system()=='Linux':
	vid = cv2.VideoCapture(0)
	webcam_found = vid.isOpened()

if webcam_found:

	# Webcam properties
	vid.set(cv2.CAP_PROP_FRAME_WIDTH, frame_width)
	vid.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_height)
	#vid.set(cv2.CAP_PROP_FPS, 30)

	# MediaPipe init
	mp_drawing = mp.solutions.drawing_utils
	mp_hands   = mp.solutions.hands
	hands      = mp_hands.Hands(min_detection_confidence=0.8, min_tracking_confidence=0.5, max_num_hands=2)

	focal_length = frame_width * 0.75
	distortion = np.zeros((4, 1))
	center = (frame_width/2, frame_height/2)
	camera_matrix = np.array(
						 [[focal_length, 0, center[0]],
						 [0, focal_length, center[1]],
						 [0, 0, 1]], dtype = 'double'
						 )

	mp_hands_options = {
					'frame_width': frame_width,
					'frame_height': frame_height,
					'camera_matrix': camera_matrix,
					'focal_length': focal_length,
					'distortion': distortion,
					'center': center,
					'apply_filter': True,
					'one_euro_min_cutoff': 0.004,
					'one_euro_beta': 20,
					'inc': 0,
					'filtered_vals': {},
					'mp_data_filter': {},
					'draw_skeleton': True,
				}

	# initialize info dictionary (image width/height etc)
	info = {}
	info['image_width'] = int(vid.get(cv2.CAP_PROP_FRAME_WIDTH))
	info['image_height'] = int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT))

	# Main UI loop
	while dpg.is_dearpygui_running():

		# read webcam frame
		success, frame = vid.read()

		if success:

			# flip video?
			if dpg.get_value('flip'): frame = cv2.flip(frame, 1)

			# Encode image to jpg (faster streams) and BGR -> RGB
			img_jpg = cv2.imencode('.jpg', frame, params=[cv2.IMWRITE_JPEG_QUALITY, 85])[1]
			data = cv2.imdecode(img_jpg, cv2.IMREAD_COLOR)
			data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB) # convert RGB
			
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
					mp_hands_options['inc'] += 1
					mp_hands_options['apply_filter'] = stream['apply_filter']
					mp_hands_options['one_euro_beta'] = stream['beta']
					joints, data = process_mp_hands.process(mp_hands=mp_hands, hands=hands, img=data, options=mp_hands_options, mp_drawing=mp_drawing)
					joints_json = json.dumps(joints)
					skt.sendto(joints_json.encode(), addr_port)

			# DPG webcam texture update: convert to 32bit float, flatten and normalize 
			data = np.asfarray(data.ravel(), dtype='f')
			texture_data = np.true_divide(data, 255.0)
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
