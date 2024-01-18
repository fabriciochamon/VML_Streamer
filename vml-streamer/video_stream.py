import cv2, platform, time, numpy as np
import dearpygui.dearpygui as dpg
from threading import Thread
import dpg_callback

class VideoStream:

	def __init__(self, size=1):
		self.stream = None
		self.set_counter = False
		self.change_source(source_type='none')
		#self.change_source(source_type='webcam', source_file=0, size=size)
		
	def get_capture_api(self):
		chosen_api = dpg.get_value('cv_vid_cap_api')
		apis = {
			'First available': cv2.CAP_ANY,
			'Direct Show': cv2.CAP_DSHOW,
			'V4L2': cv2.CAP_V4L2,
		}

		try: ret_api = apis[chosen_api]
		except: ret_api = cv2.CAP_ANY

		return ret_api

	def start(self):
		if self.source_type != 'none': 
			self.t = Thread(target=self.update, args=())
			self.t.start()
		return self

	def update(self):
		start_time = time.time()
		counter = 0
		fps_update_rate_sec = 1

		while True:

			# if stopped break loop
			if self.stopped: 
				if self.stream: self.stream.release()
				return

			# set video frame
			if self.source_type=='video': self.stream.set(cv2.CAP_PROP_POS_FRAMES, int(self.frameNumber))
			
			# read image
			try: (self.grabbed, self.frame) = self.stream.read()
			except: self.grabbed=False

			# calc fps
			if self.source_type=='webcam':
				counter+=1
			else:
				if self.set_counter:  
					counter+=1
					self.set_counter = False
			if (time.time() - start_time) > fps_update_rate_sec:
				self.fps = counter / (time.time() - start_time)
				counter = 0
				start_time = time.time()

			
	def read(self):
		if self.source_type != 'none':
			ret = (False, None)
			try: 
				ret = (self.grabbed, self.frame)
				if self.size!=1:
					frame_resized = cv2.resize(self.frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
					ret = (self.grabbed, frame_resized)
			except: 
				pass
		else:
			ret = (True, np.zeros((self.width, self.height)))

		return ret
	
	def stop(self):
		if self.source_type != 'none':
			self.stopped = True
			self.t.join(timeout=5)
			self.stream=None
			self.t=None
		else:
			self.stopped = True
			self.stream=None

	def isOpened(self):
		isOpened = True
		if self.source_type != 'none':  isOpened = self.stream.isOpened()

		return isOpened

	def change_source(self, source_type='webcam', source_file=0, size=1):
		if self.stream is not None and self.stream.isOpened(): self.stop()

		self.source_type = source_type
		self.source_file = source_file
		self.frames = 0
		self.frameNumber  = 0
		self.source_fps = 0
		self.size = self.size = float(dpg.get_value('video_size')) if dpg.does_alias_exist('video_size') else size	
		vcap_api = self.get_capture_api()

		# generates an empty (black) video frame
		if self.source_type=='none' or self.source_file=='None':
			self.source_type = 'none'
			self.capture_width  = 320
			self.capture_height = 240
			self.width  = int(self.capture_width*self.size)
			self.height = int(self.capture_height*self.size)

			if dpg.does_alias_exist('playback_controls'): dpg.hide_item('playback_controls')
			if dpg.does_alias_exist('camera_controls'): dpg.show_item('camera_controls')

			if dpg.does_alias_exist('video_image'): dpg.hide_item('video_image')
			if dpg.does_alias_exist('video_image_empty'): dpg.show_item('video_image_empty')

		# read webcam
		elif self.source_type=='webcam':
			self.stream = cv2.VideoCapture(int(source_file), vcap_api)

			# grab single frame to read webcam resolution
			success = False
			while not success: 
				success, info_frame = self.stream.read()

			self.capture_width  = info_frame.shape[1]
			self.capture_height = info_frame.shape[0]
			self.width  = int(self.capture_width*self.size)
			self.height = int(self.capture_height*self.size)
			
			if dpg.does_alias_exist('playback_controls'): dpg.hide_item('playback_controls')
			if dpg.does_alias_exist('camera_controls'): dpg.show_item('camera_controls')

			if dpg.does_alias_exist('video_image'): dpg.show_item('video_image')
			if dpg.does_alias_exist('video_image_empty'): dpg.hide_item('video_image_empty')
			
		# read video file
		elif self.source_type=='video':
			self.stream = cv2.VideoCapture(source_file, vcap_api)
			self.frames = self.stream.get(cv2.CAP_PROP_FRAME_COUNT)
			self.source_fps = self.stream.get(cv2.CAP_PROP_FPS)
			if self.source_fps <=0: self.source_fps = 24
			if dpg.does_alias_exist('fps_playback'): dpg.set_value('fps_playback', int(self.source_fps))

			self.capture_width  = self.stream.get(cv2.CAP_PROP_FRAME_WIDTH)
			self.capture_height = self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT)
			self.width = int(self.capture_width*self.size)
			self.height =int(self.capture_height*self.size)

			if dpg.does_alias_exist('cv_frame'): 
				dpg.configure_item('cv_frame', width=self.width, height=self.height)
				dpg.configure_item('video_frame', max_value=int(self.frames-1))

			if dpg.does_alias_exist('playback_controls'): dpg.show_item('playback_controls')
			if dpg.does_alias_exist('camera_controls'): dpg.hide_item('camera_controls')
			if dpg.does_alias_exist('webcam_device_number'): dpg.set_value('webcam_device_number', 'None')

			if dpg.does_alias_exist('video_image'): dpg.show_item('video_image')
			if dpg.does_alias_exist('video_image_empty'): dpg.hide_item('video_image_empty')

		dpg_callback.recreate_raw_texture(self.width, self.height)
		dpg_callback.resize_viewport(self.width)

		if self.source_type=='none':
			if dpg.does_alias_exist('video_image'): dpg.hide_item('video_image')
			if dpg.does_alias_exist('video_image_empty'): dpg.show_item('video_image_empty')
			dpg.set_viewport_width(450)
			dpg.set_viewport_height(720)

		self.stopped = False
		self.fps = 0
		
		self.start()

	def load_video_file(self, filename_list, cancel_pressed):
		if len(filename_list) and not cancel_pressed:
			# change to none, then to file... this is to avoid dpg crashes
			self.change_source(source_type='none')
			self.change_source(source_type='video', source_file=filename_list[0])
