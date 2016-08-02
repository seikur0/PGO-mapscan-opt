# PGO-mapscan-opt

## Instructions
* Edit the 'usersettings.json' file in the res subfolder to your liking.
  * The first 'profile' has to be edited and if you want the map functionality the 'api_key' setting as well. Profiles with same ids form a scan group. They use the location from the first profile in that group.
* 'pip install -r requirements.txt'
  * if it fails 'pip install --user -r requirements.txt' (mostly for unix systems)
  * if it still fails and you're using windows, you may need to install these runtimes from Microsoft: http://aka.ms/vcpython27
* 'python main0.py' to run the program

* 'python -m SimpleHTTPServer 8000' to run the local map server and make it accessible from your browser
* Open browser to 'http://localhost:8000'
  * If you get a socket bind error, choose a different port number instead of 8000

* If you wish to use pushbullet you will need an API key from https://www.pushbullet.com/#settings
  * Add that api key and the pokemon ids you wish to be notified about to the settings file

## Informations
* This scanning algorithm is all about hexagons. By interpreting the cirle created by the sight radius of 100m as a hexagon, you can fill the room of scan areas with ~80% efficiency in comparison to the base api demo, which had about 40%. The algorithm scans areas from a center point towards the outside in a circle/spiral pattern, so the whole scan area is approximately a circle as well, actually a kind of hexagon again. Furthermore I optimized the code, so it uses less resources and is also stable. No matter which bugs Niantic might have, it shouldn't crash and continue to scan if possible. Also multithreading now.

* Arguments are not required, but if used, they overwrite the settings in the 'usersettings.json' file, standard id without arguments is 0
  * '-id': is the id of the worker(s) and determines stuff like the name of the output files and the place where it will scan, account settings are read from the 'usersettings.json' file
  * '-r': is the radius around the center scanning point in hexagon layers, real radius is approximately 175r in m
  * '-t': is the minimum time interval between scans
  * '-lat': latitude
  * '-lng': longitude
  * '-alt': altitude
  * '-loc': location, you can specify the name of a location and the coordinates will be set to that, overwrites -lat and -lng

## What to do with collected data
* 'python collector.py' will upload the backed up spawn files and share them
* I was asked to include that tool by Kostronor, for more informations see https://github.com/seikur0/PGO-mapscan-opt/issues/14

## Updated stuff
* Awesome settings file for great flexibility
* Auto-backup of files greater than 10 MB, can be tweaked or disabled
* Can tweak most settings with the fully optional arguments
* Pushbullet support also for multiple receivers
* Multithreading (way to small entry for this awesome feature)
* Accounts not being able to log in was fixed (some people had problems)

## FAQ
* https://github.com/seikur0/PGO-mapscan-opt/blob/master/FAQ.txt
  * I will collect questions, when I answer them the first time, and then I'll include a FAQ in the files here on github.
  * Don't think I'm impolite, when I'll just answer FAQ to something you write me. It's just that I want to do more with my day than answering the same questions over and over again :)
  * Suggestions and feedback in general are very welcome though, that helps me in finding bugs and improvements.

## Thanks

To Tejado, who made the original pokemongo api demo, which I based my project on: https://github.com/tejado/pgoapi

To AeonLucid for creating and expanding the POGO Protos Library: https://github.com/AeonLucid/POGOProtos

To HEKTakun, I'm using his awesome pokemon icons for the map.

##Visualization of the algorithm

Check out the github page of lordbaconcake, it visualizes the beauty of the hexagon algorithm quite well.
And if you'd like to cover more complex or square areas rather than a circle-like pattern, check out his api.
https://github.com/spezifisch/geoscrape
