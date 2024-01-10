<!-- Splash logo
![VML Streamer Splash](assets/images/vml_streamer_splash.png)
-->

# VML_Streamer
Vision and Machine Learning data streamer for Houdini

---

## Virtual environment:
Note: `pip install -r requirements.txt` can potentially give you errors 
(due to how specific module versions were frozen on Windows/Linux machines).

So consider running this as an alternative to build your virtual environment:  
*(Tested on Python 3.10.\*)*

	# create venv
	cd VML_Streamer
	python -m venv venv

	# activate venv
	source venv/bin/activate # on Linux
	venv/Scripts/activate    # on Windows
	
	# install modules ("pyinstaller" only needed if you'll build binaries)
	pip install opencv-python mediapipe dearpygui dearpygui_extend pyinstaller

## Running:

	# with venv activated, run main program	
	cd vml-streamer
	python main.py

<br/><br/>
![VML Streamer Screenshot](assets/images/vml_streamer.png)
