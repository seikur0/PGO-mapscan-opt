# PGO-mapscan-opt

## Instructions
* Put your username(s)/password(s) into the main0.py file (line 96 and 97)
* Put your scan location into the main0.py file (line 79) as latitude, longitude,altitude (you can put in 0 for the last one)
* If you want english names instead of german ones, edit LANGUAGE (line 93)
* `pip install -r requirements.txt`
* `python main0.py -id 0 -r 20 -t 600`


* If you want the map visualization, put your Google API Browser key into the html file (line 163) (you can get one for free)
* Also put your scan location into the index.html file (line 27/28), only latitude, longitude this time
* Again if you want english names instead of german ones, edit LANGUAGE (line 29)
* You should also modify the excludeIDs variable (line 30), pokemon with these ids won't be shown on the map, hint: leave in Pidgey ;)
* `python -m SimpleHTTPServer 8000`
* Open browser to `http://localhost:8000`

## Informations
* This scanning algorithm is all about hexagons. By interpreting the cirle created by the sight radius of 100m as a hexagon, you can fill the room of scan areas with ~80% efficiency in comparison to the base api demo, which had about 40%. The algorithm scans areas from a center point towards the outside in a circle/spiral pattern, so the whole scan area is approximately a circle as well, actually a kind of hexagon again. Furthermore I optimized the code, so it uses less resources and is also stable. No matter which bugs Niantic might have, it shouldn't crash and continue to scan if possible.
* `id argument`: is the id of the worker and determines stuff like the name of the output files and the place where it will scan, so when id 0 scans a huge hexagon, id1-id6 will scan the hexagons directly around it, higher than 6 is not implemented as of now
* `r argument`: is the radius around the center scanning point in hexagon layers, real radius varies from (173.2r+86.6) to 150r+100
* `t argument`: is the minimum time interval between scans, can go higher, if pgo servers are slow, but they seem stable for now

## Thanks

To Tejado, who made the original pokemongo api demo, which I based my project on: https://github.com/tejado/pgoapi

To AeonLucid for creating and expanding the POGO Protos Library: https://github.com/AeonLucid/POGOProtos

To HEKTakun, I'm using his awesome pokemon icons for the map.


##Visualization of the algorithm

Check out the github page of lordbaconcake, it visualizes the beauty of the hexagon algorithm quite well.
And if you'd like to cover more complex or square areas rather than a circle-like pattern, check out his api.
https://github.com/spezifisch/geoscrape
