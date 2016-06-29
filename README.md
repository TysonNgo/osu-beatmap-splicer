# osu-beatmap-splicer
osu-beatmap-splicer is a tool for the rhythm game osu! that will produce an executable beatmap file (.osz) containing meshed sections of beatmaps specified in the settings.txt.

# Setup
To use the osu! beatmap splicer, [pydub](http://pydub.com/) must be installed and [ffmpeg](https://ffmpeg.org/download.html) is required.
```
pip install pydub
```


### settings.txt
There are three headers in settings.txt, *Settings*, *osu!Files*, and *BeatmapSections*.

*Settings* contains the path to ffmpeg, song information, difficulty settings, and break time between sections in milliseconds of the final beatmap to be produced.

*osu!Files* contains the path(s) to beatmap file(s) (.osu).

*BeatmapSections* contains the time of the beatmap section. This is obtained by going into the in-game beatmap editor and highlighting a section of the beatmap of interest and then copying that selection to the clipboard.

note: A line in *osu!Files* and *BeatmapSections* containing a single asterisk (\*) denotes a copy of the previous line.

ie.
```
  [osu!Files]
  C:/Program Files/osu!/Songs/beatmap_folder/file.osu
  *
  
  [BeatmapSections]
  00:00:000 (1,2,3,4,5,6,7) - 
  *
```
translates to:
```
  [osu!Files]
  C:/Program Files/osu!/Songs/beatmap_folder/file.osu
  C:/Program Files/osu!/Songs/beatmap_folder/file.osu
  
  [BeatmapSections]
  00:00:000 (1,2,3,4,5,6,7) - 
  00:00:000 (1,2,3,4,5,6,7) - 
```

### beatmap_template.osu

This is used as a template for the final resulting beatmap file, do **not** delete this file.
