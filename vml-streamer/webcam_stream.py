import cv2, platform, time
from threading import Thread

class WebcamVideoStream:

	def __init__(self, src=0, width=None, height=None):
		vcap_api = cv2.CAP_ANY
		if platform.system()=='Windows': vcap_api = cv2.CAP_DSHOW
		if platform.system()=='Linux':   vcap_api = cv2.CAP_V4L2
		self.stream = cv2.VideoCapture(src, vcap_api)
		if width:  self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
		if height: self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
		(self.grabbed, self.frame) = self.stream.read()
		self.stopped = False
		self.fps = 0

	def start(self):
		Thread(target=self.update, args=()).start()
		return self

	def update(self):
		start_time = time.time()
		counter = 0
		fps_update_rate_sec = 1

		while True:
			if self.stopped: return
			(self.grabbed, self.frame) = self.stream.read()

			# calc fps
			counter+=1
			if (time.time() - start_time) > fps_update_rate_sec:
				self.fps = counter / (time.time() - start_time)
				counter = 0
				start_time = time.time()
	
	def read(self):
		return (self.grabbed, self.frame)
	
	def stop(self):
		self.stopped = True
		self.stream.release()
	
	def isOpened(self):
		return self.stream.isOpened()