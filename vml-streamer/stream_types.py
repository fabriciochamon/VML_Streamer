ST_INFO_DICT = 'Info Dictionary'
ST_WEBCAM    = 'Webcam'
ST_MP_HANDS  = 'MediaPipe Hands'
ST_MP_BODY   = 'MediaPipe Body'

ALL          = [v for k,v in globals().items() if k.startswith('ST_')]