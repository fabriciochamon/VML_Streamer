import cv2, mediapipe as mp
import numpy as np
from one_euro_filter import OneEuroFilter

def process(mp_hands, hands, img, options, mp_drawing):

	# prep img
	img.flags.writeable=False
	results = hands.process(img)
	img.flags.writeable=True
	mp_data = {}

	if results.multi_hand_landmarks:

		# loop through found hands
		for i, mp_hand in enumerate(results.multi_hand_landmarks):

			# get landmarks
			world_landmarks = results.multi_hand_world_landmarks[i]

			# convert to proper 3d world coordinates
			###################################################################################################
			# thanks to Fryderyk Kogl
			# for providing this code: https://github.com/google/mediapipe/issues/2199#issuecomment-1172971018
			###################################################################################################
			model_points = np.float32([[-l.x, -l.y, -l.z] for l in world_landmarks.landmark])
			image_points = np.float32([[l.x * options['frame_width'], l.y * options['frame_height']] for l in mp_hand.landmark])
			success, rotation_vector, translation_vector = cv2.solvePnP(model_points, image_points, options['camera_matrix'], options['distortion'], flags=cv2.SOLVEPNP_SQPNP)
			transformation = np.eye(4)
			transformation[0:3, 3] = translation_vector.squeeze()
			model_points_hom = np.concatenate((model_points, np.ones((21, 1))), axis=1)
			world_points = model_points_hom.dot(np.linalg.inv(transformation).T)

			# draw landmarks over cv image
			if options['draw_skeleton']:
				mp_drawing.draw_landmarks(img, mp_hand, mp_hands.HAND_CONNECTIONS)

			# populate hand dict
			hand_name = results.multi_handedness[i].classification[0].label
			mp_data[hand_name] = []
			for n, lm in enumerate(world_points):
				
				# apply one-euro-filter to smooth signal
				for m in range(3):
					options['filtered_vals'][f'{hand_name}{n}{m}'] = lm[m]	

					if options['apply_filter']:
						if f'{hand_name}{n}{m}' not in options['mp_data_filter'].keys():
							options['mp_data_filter'][f'{hand_name}{n}{m}']=OneEuroFilter(options['inc'], lm[m], min_cutoff=options['one_euro_min_cutoff'], beta=options['one_euro_beta'])
							options['filtered_vals'][f'{hand_name}{n}{m}'] = lm[m]
						else:
							try:
								options['filtered_vals'][f'{hand_name}{n}{m}'] = options['mp_data_filter'][f'{hand_name}{n}{m}'](options['inc'], lm[m])
								if np.isnan(options['filtered_vals'][f'{hand_name}{n}{m}']):
									options['mp_data_filter'][f'{hand_name}{n}{m}']=OneEuroFilter(options['inc'], lm[m], min_cutoff=options['one_euro_min_cutoff'], beta=options['one_euro_beta'])
									options['filtered_vals'][f'{hand_name}{n}{m}'] = lm[m]	
							except:
								options['filtered_vals'][f'{hand_name}{n}{m}'] = lm[m]	

				# set dict
				mp_data[hand_name].append(
					{
						'x':options['filtered_vals'][f'{hand_name}{n}0'],
						'y':options['filtered_vals'][f'{hand_name}{n}1'],
						'z':options['filtered_vals'][f'{hand_name}{n}2'],
					}
				)

	return (mp_data, img)