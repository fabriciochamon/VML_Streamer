import cv2, platform, time
import dearpygui.dearpygui as dpg
from threading import Thread
import dpg_callback

class VideoStream:

	def __init__(self, width=320, height=240):
		self.stream = None
		self.set_counter = False
		self.change_source(source_type='webcam', source_file=0, width=width, height=height)
		
	def get_capture_api(self):
		vcap_api = cv2.CAP_ANY
		if platform.system()=='Windows': vcap_api = cv2.CAP_DSHOW
		if platform.system()=='Linux':   vcap_api = cv2.CAP_V4L2
		return vcap_api

	def start(self):
		self.t = Thread(target=self.update, args=())
		self.t.start()
		return self

	def update(self):
		start_time = time.time()
		counter = 0
		fps_update_rate_sec = 1

		while True:
			if self.stopped: 
				if self.stream: self.stream.release()
				return

			if self.source_type=='video': self.stream.set(cv2.CAP_PROP_POS_FRAMES, int(self.frameNumber))
			
			(self.grabbed, self.frame) = self.stream.read()

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
		return (self.grabbed, self.frame)
	
	def stop(self):
		self.stopped = True
		self.t.join(timeout=5)
		self.stream=None
		self.t=None
	
	def isOpened(self):
		return self.stream.isOpened()

	def change_source(self, source_type='webcam', source_file=0, width=320, height=240):
		if self.stream is not None and self.stream.isOpened(): self.stop()

		self.source_type = source_type
		self.source_file = source_file
		self.frames = 0
		self.frameNumber  = 0
		self.source_fps = 0
		vcap_api = self.get_capture_api()

		if source_type=='webcam':
			self.stream = cv2.VideoCapture(source_file, vcap_api)
			self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
			self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
			res = (width, height)
			self.width = int(res[0])
			self.height = int(res[1])
			if dpg.does_alias_exist('playback_controls'): dpg.hide_item('playback_controls')
			if dpg.does_alias_exist('camera_controls'): dpg.show_item('camera_controls')
			
		elif source_type=='video':
			self.stream = cv2.VideoCapture(source_file)
			self.frames = self.stream.get(cv2.CAP_PROP_FRAME_COUNT)
			self.source_fps = self.stream.get(cv2.CAP_PROP_FPS)
			if self.source_fps <=0: self.source_fps = 24
			dpg.set_value('fps_playback', int(self.source_fps))
			res = (self.stream.get(cv2.CAP_PROP_FRAME_WIDTH), self.stream.get(cv2.CAP_PROP_FRAME_HEIGHT))
			self.width = int(res[0])
			self.height = int(res[1])
			dpg.configure_item('cv_frame', width=self.width, height=self.height)
			dpg.configure_item('video_frame', max_value=int(self.frames-1))
			if dpg.does_alias_exist('playback_controls'): dpg.show_item('playback_controls')
			if dpg.does_alias_exist('camera_controls'): dpg.hide_item('camera_controls')
			dpg.set_value('webcam_device_number', 'None')
			
		dpg_callback.recreate_raw_texture(self.width, self.height)
		#dpg_callback.resize_viewport(self.width)

		self.stopped = False
		self.fps = 0
		
		self.start()
