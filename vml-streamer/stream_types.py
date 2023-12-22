ST_INFO_DICT = 'Info Dictionary'
ST_VIDEO     = 'Video'
ST_MP_HANDS  = 'MediaPipe Hands'
ST_MP_BODY   = 'MediaPipe Body'
ST_MP_FACE   = 'MediaPipe Face'

ALL          = [v for k,v in globals().items() if k.startswith('ST_')]