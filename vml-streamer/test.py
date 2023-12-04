import cv2, numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2

MARGIN = 10  # pixels
FONT_SIZE = 1
FONT_THICKNESS = 1
HANDEDNESS_TEXT_COLOR = (88, 205, 54) # vibrant green

def draw_landmarks_on_image(rgb_image, detection_result):
	hand_landmarks_list = detection_result.hand_landmarks
	handedness_list = detection_result.handedness
	annotated_image = np.copy(rgb_image)

	# Loop through the detected hands to visualize.
	for idx in range(len(hand_landmarks_list)):
		hand_landmarks = hand_landmarks_list[idx]
		handedness = handedness_list[idx]

		# Draw the hand landmarks.
		hand_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
		hand_landmarks_proto.landmark.extend([
		  landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in hand_landmarks
		])
		solutions.drawing_utils.draw_landmarks(
		  annotated_image,
		  hand_landmarks_proto,
		  solutions.hands.HAND_CONNECTIONS,
		  solutions.drawing_styles.get_default_hand_landmarks_style(),
		  solutions.drawing_styles.get_default_hand_connections_style())

		# Get the top left corner of the detected hand's bounding box.
		height, width, _ = annotated_image.shape
		x_coordinates = [landmark.x for landmark in hand_landmarks]
		y_coordinates = [landmark.y for landmark in hand_landmarks]
		text_x = int(min(x_coordinates) * width)
		text_y = int(min(y_coordinates) * height) - MARGIN

		# Draw handedness (left or right hand) on the image.
		cv2.putText(annotated_image, f"{handedness[0].category_name}",
					(text_x, text_y), cv2.FONT_HERSHEY_DUPLEX,
					FONT_SIZE, HANDEDNESS_TEXT_COLOR, FONT_THICKNESS, cv2.LINE_AA)

	return annotated_image

base_options = python.BaseOptions(model_asset_path='mediapipe_models/hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
detector = vision.HandLandmarker.create_from_options(options)

vid = cv2.VideoCapture(0, cv2.CAP_ANY)
if vid.isOpened():
	while True:
		success, frame = vid.read()

		img_jpg = cv2.imencode('.jpg', frame, params=[cv2.IMWRITE_JPEG_QUALITY, 85])[1]
		data = cv2.imdecode(img_jpg, cv2.IMREAD_COLOR)
		data = cv2.cvtColor(data, cv2.COLOR_BGR2RGB) # convert RGB
		image = mp.Image(mp.ImageFormat.SRGB, data=data)

		detection_result = detector.detect(image)
		annotated_image = draw_landmarks_on_image(image.numpy_view(), detection_result)
		
		data = cv2.cvtColor(annotated_image, cv2.COLOR_RGB2BGR) # convert RGB
		cv2.imshow('webcam', data)

		if cv2.waitKey(1) & 0xFF == ord('q'):
			break
