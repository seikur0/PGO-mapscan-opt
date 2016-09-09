# PGO-mapscan-opt

## Instructions
* Rename 'usersettings.json.example' in the res subfolder to 'usersettings.json' and edit the file to your liking.
  * The first 'profile' has to be edited and if you want the map functionality the 'api_key' setting as well. Profiles with same ids form a scan group. They use the location and the (optional) proxy from the first profile in that group.
* 'pip install -r requirements.txt'
  * if it fails 'pip install --user -r requirements.txt' (mostly for unix systems) or try to sudo it
  * if it fails and you're using windows, you may need to install these runtimes from Microsoft: http://aka.ms/vcpython27
  * if you have trouble with these Microsoft VC runtimes, get the wheel for the problematic package directly, for example from here: http://www.lfd.uci.edu/~gohlke/pythonlibs/ and install it directly with pip
* With the unknown6 now being required you need a library file named 'encrypt.so'.
  * As for instructions how to get it, please look here: https://github.com/PokemonGoF/PokemonGo-Bot/issues/2966
  * Or get it directly here (windows): https://github.com/PokemonGoMap/PokemonGo-Map/tree/develop/pogom/libencrypt
  * When you have the appropriate file (32 bit for 32 bit Python installed!), name it 'encrypt.so' and put it into the res subfolder.
* 'python main0.py' to run the program
* intelligent spawn point scanning:
  * let it run for one hour at max and it'll write the scan data like empty cells/spawnpoints/forts into a file
  * during that time the scan time should stay below 10 minutes, below 15 minutes may work too, no guarantee though. if it's longer than that, consider reducing range or add more workers (normally you don't have any undefined/"-1" points at the end)
* customize scan area:
  * You can use the spawnfix.py file to merge all learning files in its folder into one, then rename that 'mapdata.json' file to fit the parameters of some of your profiles, for example "123.1234_1.1234_30_70.0.json" and it'll scan all the points.
  * You can use https://github.com/brandonshults/pipoam to visualize the whole area and fine select, which points you want, don't ask me for support on it, figure it out yourself or don't use it ;)
* recent change from s to ms unit in learning files:
  * Use spawnfix.py to migrate your old learning files to the new format

* Execute "python pokesite.py" to host the website with your map on 'http://localhost:8000'.
* That port can be changed in the settings file.
  * If you get a socket bind error, choose a different port number instead of 8000.

* If you wish to use pushbullet notifications you will need an API key from https://www.pushbullet.com/#settings
  * Add that api key and the pokemon ids you wish to be notified about to the settings file
* If you wish to use telegram notifications you will need to create a bot and put the token and channel into the settings, google it

## Features
* uses hexagon algorithm for normal scanning
* after maximally one hour of normal scanning, it saves a spawnpoint file and starts intelligent scan (iscan)
* iscan = spawnpoints are scanned directly after spawn (no wasted scans and very efficient)
* perfect recognition and support for all spawn point types for both the logging and the map
* iscan uses much less workers
* multithreading
* long term stable
* perfect for data logging, has an autobackup function
* individual proxy possible for each id
* very good hosted map site, mobile optimized
* very low data usage (perfect for mobiles)
* pushbullet and telegram notifications
* many more small things that contribute to a smooth user experience

* Arguments are not required, but if used, they overwrite the settings in the 'usersettings.json' file, standard id without arguments is 0
  * '-id': is the id of the worker(s) and determines stuff like the name of the data log file and the place where it will scan, account settings are read from the 'usersettings.json' file
  * '-r': is the radius around the center scanning point in hexagon layers, real radius is approximately 175r in m
  * '-t': is the minimum time interval between scans
  * '-lat': latitude
  * '-lng': longitude
  * '-alt': altitude
  * '-loc': location, you can specify the name of a location and the coordinates will be set to that, overwrites -lat and -lng
  * '-s': scans, will quit after the specified number of scans, 1 for single scans
  * '-tos': use this argument to make all accounts accept the tos at the start (only needed once for new accounts)

## What to do with collected data
* 'python collector.py' will upload the backed up spawn files and share them
* I was asked to include that tool by Kostronor, for more informations see https://github.com/seikur0/PGO-mapscan-opt/issues/14

## FAQ
* https://github.com/seikur0/PGO-mapscan-opt/blob/master/FAQ.txt
  * I will collect questions, when I answer them the first time, and then I'll include a FAQ in the files here on github.
  * Don't think I'm impolite, when I'll just answer FAQ to something you write me. It's just that I want to do more with my day than answering the same questions over and over again :)
  * Suggestions and feedback in general are very welcome though, that helps me in finding bugs and improvements.

## Thanks

To Tejado, who made the original pokemongo api demo, which I based my project on: https://github.com/tejado/pgoapi

To AeonLucid for creating and expanding the POGO Protos Library: https://github.com/AeonLucid/POGOProtos

To the heroes of the unknown6 team.

To HEKTakun, I'm using his awesome pokemon icons for the map.

## Visualization of the algorithm

Check out the github page of lordbaconcake, it visualizes the beauty of the hexagon algorithm quite well.
And if you'd like to cover more complex or square areas rather than a circle-like pattern, check out his api.
https://github.com/spezifisch/geoscrape
