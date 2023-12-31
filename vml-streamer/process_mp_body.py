import cv2, mediapipe as mp
import numpy as np
import platform
from one_euro_filter import OneEuroFilter
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions
from mediapipe.tasks import python as tasks
from mediapipe.tasks.python import vision
import resources

class MediaPipe_Bodies:
	def __init__(self, frame_width, frame_height):
		self.image = None
		self.display_image = np.zeros((frame_width, frame_height, 3), dtype=np.uint8)
		self.frame_width=frame_width
		self.frame_height=frame_height
		self.iteration = 0
		self.focal_length = self.frame_width * 0.75
		self.distortion = np.zeros((4, 1))
		self.center = (self.frame_width/2, self.frame_height/2)
		self.camera_matrix = np.array(
							 [[self.focal_length, 0, self.center[0]],
							 [0, self.focal_length, self.center[1]],
							 [0, 0, 1]], dtype = 'double'
							 )
		self.apply_filter = False
		self.one_euro_min_cutoff = 0.004
		self.one_euro_beta = 20
		self.filtered_vals = {}
		self.mp_data_filter = {}
		self.running_mode = vision.RunningMode.LIVE_STREAM
		delegate = tasks.BaseOptions.Delegate.GPU if platform.system()=='Linux' else tasks.BaseOptions.Delegate.CPU
		self.base_options = tasks.BaseOptions(model_asset_path=resources.getPath('mediapipe_models/pose_landmarker_full.task'), delegate=delegate)
		self.options = vision.PoseLandmarkerOptions(base_options=self.base_options, min_pose_detection_confidence=0.8, min_tracking_confidence=0.5, num_poses=1, running_mode=self.running_mode, result_callback=self.on_detection)
		self.detector = vision.PoseLandmarker.create_from_options(self.options)
		self.joints = {}
		self.draw_skeleton = True

	def on_detection(self, result: vision.PoseLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
		self.iteration +=1
		self.joints = {}

		# loop through found landmarks
		for i, pose_landmarks in enumerate(result.pose_landmarks):
			pose_world_landmarks = result.pose_world_landmarks[i]

			# draw landmarks over cv image
			self.display_image = self.image.numpy_view()
			if self.draw_skeleton:
				pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
				pose_landmarks_proto.landmark.extend([ landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in pose_landmarks ])
				solutions.drawing_utils.draw_landmarks(
					self.display_image,
					pose_landmarks_proto,
					solutions.pose.POSE_CONNECTIONS,
					solutions.drawing_styles.get_default_pose_landmarks_style(),
					)
				
			# populate body dict
			pose_name = f'Body{i}'
			self.joints[pose_name] = []

			for n, lm in enumerate(pose_world_landmarks):
			
				self.joints[pose_name].append(
					{
						'x': lm.x,
						'y': lm.y,
						'z': lm.z,
					}
				)

	def detect(self, timestamp):
		self.detector.detect_async(image=self.image, timestamp_ms=timestamp)
		
