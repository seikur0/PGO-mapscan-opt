# PGO-mapscan-opt

## Instructions
* Edit the 'usersettings.json' file in the res subfolder to your liking. Don't worry, if you don't understand every setting, some are for more specific uses.
  * 'standard_coordinates' and the first 'profile' have to be edited and if you want the map functionality the 'api_key' setting as well
* 'pip install -r requirements.txt' or if that fails 'pip install --user -r requirements.txt'
* 'pip install pushbullet.py' to install the pushbullet API
* You will need an API key from https://www.pushbullet.com/#settings
* Make sure to add the Pokemon ID's you want to be notifuied about to the configuration file
* 'python main0.py' to run the program

* 'python -m SimpleHTTPServer 8000' to run the local map server and make it accessible from your browser
* Open browser to 'http://localhost:8000'
* If you get a socket bind error, choose a different port number instead of 8000

## Informations
* This scanning algorithm is all about hexagons. By interpreting the cirle created by the sight radius of 100m as a hexagon, you can fill the room of scan areas with ~80% efficiency in comparison to the base api demo, which had about 40%. The algorithm scans areas from a center point towards the outside in a circle/spiral pattern, so the whole scan area is approximately a circle as well, actually a kind of hexagon again. Furthermore I optimized the code, so it uses less resources and is also stable. No matter which bugs Niantic might have, it shouldn't crash and continue to scan if possible.

* Arguments are not required, but if used, they overwrite the settings in the 'usersettings.json' file, standard id without arguments is 0
* '-id': is the id of the worker and determines stuff like the name of the output files and the place where it will scan, settings are read from the 'usersettings.json' file, in centralscan is set to true, id 0 scans a hexagon and id1-id6 will scan the hexagons directly around it
* '-r': is the radius around the center scanning point in hexagon layers, real radius is approximately 175r in m
* '-t': is the minimum time interval between scans
* '-lt': login type, can be 'ptc' or 'google'
* '-u': username
* '-p': password
* '-lat': latitude
* '-lng': longitude
* '-alt': altitude

## Updated stuff
* Google Login is now fully working
* Awesome settings file for great flexibility
* Auto-backup of files greater than 10 MB, can be tweaked or disabled
* Can tweak most settings with the fully optional arguments
* Fixed some bad chars in the 'english.json' file

## Thanks

To Tejado, who made the original pokemongo api demo, which I based my project on: https://github.com/tejado/pgoapi

To AeonLucid for creating and expanding the POGO Protos Library: https://github.com/AeonLucid/POGOProtos

To HEKTakun, I'm using his awesome pokemon icons for the map.

##Visualization of the algorithm

Check out the github page of lordbaconcake, it visualizes the beauty of the hexagon algorithm quite well.
And if you'd like to cover more complex or square areas rather than a circle-like pattern, check out his api.
https://github.com/spezifisch/geoscrape
