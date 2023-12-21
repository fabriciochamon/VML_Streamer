import cv2, mediapipe as mp
import numpy as np
import platform
from one_euro_filter import OneEuroFilter
from mediapipe.framework.formats import landmark_pb2
from mediapipe import solutions
from mediapipe.tasks import python as tasks
from mediapipe.tasks.python import vision
import resources

class MediaPipe_Faces:
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
		self.base_options = tasks.BaseOptions(model_asset_path=resources.getPath('mediapipe_models/face_landmarker.task'), delegate=delegate)
		self.options = vision.FaceLandmarkerOptions(
			base_options=self.base_options, 
			output_facial_transformation_matrixes=True, 
			min_face_detection_confidence=0.8, 
			min_tracking_confidence=0.5, 
			num_faces=1, 
			running_mode=self.running_mode, 
			result_callback=self.on_detection)
		self.detector = vision.FaceLandmarker.create_from_options(self.options)
		self.joints = {}
		self.draw_skeleton = False

	def on_detection(self, result: vision.FaceLandmarkerResult, output_image: mp.Image, timestamp_ms: int):
		self.iteration +=1
		self.joints = {}

		# loop through found faces
		for i, face_landmarks in enumerate(result.face_landmarks):

			# get landmarks
			face_world_landmarks = result.facial_transformation_matrixes[i]
			
			# draw landmarks over cv image
			self.display_image = self.image.numpy_view()
			if self.draw_skeleton:
				face_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
				face_landmarks_proto.landmark.extend([ landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in face_landmarks ])
				solutions.drawing_utils.draw_landmarks(
					self.display_image,
					face_landmarks_proto,
					solutions.face_mesh.FACEMESH_TESSELATION,
					None,
					solutions.drawing_styles.get_default_face_mesh_tesselation_style()
					)
				solutions.drawing_utils.draw_landmarks(
					self.display_image,
					face_landmarks_proto,
					solutions.face_mesh.FACEMESH_CONTOURS,
					None,
					solutions.drawing_styles.get_default_face_mesh_contours_style()
					)
				solutions.drawing_utils.draw_landmarks(
					self.display_image,
					face_landmarks_proto,
					solutions.face_mesh.FACEMESH_IRISES,
					None,
					solutions.drawing_styles.get_default_face_mesh_iris_connections_style()
					)
			
			
			# populate face dict
			face_name = f'Face{i}'
			self.joints[face_name] = []

			for lm in face_landmarks:
				self.joints[face_name].append(
						{
							'x':lm.x,
							'y':lm.y,
							'z':lm.z,
						}
					)
					

	def detect(self, timestamp):
		self.detector.detect_async(image=self.image, timestamp_ms=timestamp)
		
