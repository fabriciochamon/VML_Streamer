import cv2, mediapipe as mp
import numpy as np
import platform
from one_euro_filter import OneEuroFilter
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions
from mediapipe.tasks import python as tasks
from mediapipe.tasks.python import vision

class MediaPipe_Hands:
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
		self.apply_filter = True
		self.one_euro_min_cutoff = 0.004
		self.one_euro_beta = 20
		self.filtered_vals = {}
		self.mp_data_filter = {}
		self.running_mode = vision.RunningMode.LIVE_STREAM
		delegate = tasks.BaseOptions.Delegate.GPU if platform.system()=='Linux' else tasks.BaseOptions.Delegate.CPU
		self.base_options = tasks.BaseOptions(model_asset_path='mediapipe_models/hand_landmarker.task', delegate=delegate)
		self.options = vision.HandLandmarkerOptions(base_options=self.base_options, min_hand_detection_confidence=0.8, min_tracking_confidence=0.5, num_hands=2, running_mode=self.running_mode, result_callback=self.on_detection)
		self.detector = vision.HandLandmarker.create_from_options(self.options)
		self.joints = {}
		self.draw_skeleton = True

	def on_detection(self, result: vision.HandLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
		self.iteration +=1
		self.joints = {}

		# loop through found hands
		for i, hand_landmarks in enumerate(result.hand_landmarks):

			# get landmarks
			hand_world_landmarks = result.hand_world_landmarks[i]
			handedness = result.handedness[i]
			
			# convert to proper 3d world coordinates
			###################################################################################################
			# thanks to Fryderyk Kogl
			# for providing this code: https://github.com/google/mediapipe/issues/2199#issuecomment-1172971018
			###################################################################################################
			model_points = np.float32([[-l.x, -l.y, -l.z] for l in hand_world_landmarks])
			image_points = np.float32([[l.x * self.frame_width, l.y * self.frame_height] for l in hand_landmarks])
			success, rotation_vector, translation_vector = cv2.solvePnP(model_points, image_points, self.camera_matrix, self.distortion, flags=cv2.SOLVEPNP_SQPNP)
			transformation = np.eye(4)
			transformation[0:3, 3] = translation_vector.squeeze()
			model_points_hom = np.concatenate((model_points, np.ones((21, 1))), axis=1)
			world_points = model_points_hom.dot(np.linalg.inv(transformation).T)

			# draw landmarks over cv image
			self.display_image = self.image.numpy_view()
			if self.draw_skeleton:
				hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
				hand_landmarks_proto.landmark.extend([ landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks ])
				solutions.drawing_utils.draw_landmarks(
					self.display_image,
					hand_landmarks_proto,
					solutions.hands.HAND_CONNECTIONS,
					solutions.drawing_styles.get_default_hand_landmarks_style(),
					solutions.drawing_styles.get_default_hand_connections_style()
					)
			
			# populate hand dict
			hand_name = handedness[0].category_name
			self.joints[hand_name] = []
			for n, lm in enumerate(world_points):
				
				# apply one-euro-filter to smooth signal
				for m in range(3):
					self.filtered_vals[f'{hand_name}{n}{m}'] = lm[m]	

					if self.apply_filter:
						if f'{hand_name}{n}{m}' not in self.mp_data_filter.keys():
							self.mp_data_filter[f'{hand_name}{n}{m}'] = OneEuroFilter(self.iteration, lm[m], min_cutoff=self.one_euro_min_cutoff, beta=self.one_euro_beta)
							self.filtered_vals[f'{hand_name}{n}{m}'] = lm[m]							
						else:
							try:
								self.filtered_vals[f'{hand_name}{n}{m}'] = self.mp_data_filter[f'{hand_name}{n}{m}'](self.iteration, lm[m])
								if np.isnan(self.filtered_vals[f'{hand_name}{n}{m}']):
									self.mp_data_filter[f'{hand_name}{n}{m}'] = OneEuroFilter(self.iteration, lm[m], min_cutoff=self.one_euro_min_cutoff, beta=self.one_euro_beta)
									self.filtered_vals[f'{hand_name}{n}{m}'] = lm[m]	
							except:
								self.filtered_vals[f'{hand_name}{n}{m}'] = lm[m]	

				# set dict
				self.joints[hand_name].append(
					{
						'x':self.filtered_vals[f'{hand_name}{n}0'],
						'y':self.filtered_vals[f'{hand_name}{n}1'],
						'z':self.filtered_vals[f'{hand_name}{n}2'],
					}
				)
				
				

	def detect(self, timestamp):
		self.detector.detect_async(image=self.image, timestamp_ms=timestamp)
		
