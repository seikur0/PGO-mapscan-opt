# PGO-mapscan-opt

## Instructions
See [New User Guide (Windows)](https://github.com/seikur0/PGO-mapscan-opt/wiki/New-User-Guide-(Windows)) for a guide that is mainly windows focused.

We also have a [Discord Channel](https://discord.gg/s2esz7Z).

## Recent Changes
* recent change from s to ms unit in learning files:
  * Use spawnfix.py to migrate your old learning files to the new format
* recent path changes:
  * Learning files go into the res/learning/learn_files folder, in the settings put the name of the file you want to use for a profile into the learn_file entry (without the .json). Log files are now in the res/logs folder
* recent scan pattern changes:
  * The r parameter is now the circular scan range in m around a point. If you want to use the old hex pattern, use the '-hx' and the '-r' parameter to specify a radius in hex layers
* PokeAlarm webhooks are now fully supported, make sure to set up a custom alarm text and use the \<respawn_text\> field to see messages like '15m later back for 15m.' for 2x15 spawn points for example

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

* Arguments are not required, but if used, they overwrite the settings in the 'usersettings.json' file, the standard id without arguments is 0, see [Command Line Arguments](https://github.com/seikur0/PGO-mapscan-opt/wiki/Command-Line-Arguments)

## Help wanted
If you have any learning files created with my tool, I'd like to have them, so I can collect them and create a larger database. So if possible I'd like you to send me these files per mail: seikur00@gmail.com I'll share them somewhere, maybe Google Drive, so everyone can access them. Thanks :)

## FAQ
* [FAQ](https://github.com/seikur0/PGO-mapscan-opt/wiki/FAQ)
  * I will collect questions, when I answer them the first time, and then I'll include a FAQ in the files here on github.
  * Don't think I'm impolite, when I'll just answer FAQ to something you write me. It's just that I want to do more with my day than answering the same questions over and over again :)
  * Suggestions and feedback in general are very welcome though, that helps me in finding bugs and improvements.

## Thanks

To Tejado, who made the original pokemongo api demo, which I based my project on: https://github.com/tejado/pgoapi

To AeonLucid for creating and expanding the POGO Protos Library: https://github.com/AeonLucid/POGOProtos

To the heroes of the unknown6 team.

To HEKTakun, I'm using his awesome pokemon icons for the map.

## Image of the actual map (with most pokemon being filtered out)

![visual](https://cloud.githubusercontent.com/assets/20639004/18809142/0919b62e-8275-11e6-8d74-350eaec24fc9.png)
