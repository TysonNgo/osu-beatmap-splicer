from pydub import AudioSegment
import re
import os
from zipfile import ZipFile

class Break_Period(object):
   def __init__(self, bp_line):
      line = bp_line.split(",")
      self.event_type = int(line[0])
      self.start_time = int(line[1])
      self.end_time = int(line[2])
      
   def get_line(self):
      return str(self.event_type)+","+str(self.start_time)+","+str(self.end_time)
      
   def offset_time(self,offset):
      self.start_time += offset
      self.end_time += offset

class Timing_Point(object):
   def __init__(self, tp_line):
      line = tp_line.split(",")
      self.t = int(line[0])
      self.mspb = float(line[1])
      self.meter = int(line[2])
      self.sample_type = int(line[3])
      self.sample_set = int(line[4])
      self.volume = int(line[5])
      self.inherited = int(line[6])
      self.kiai = int(line[7])
   
   def get_line(self):
      return str(self.t)+","+str(self.mspb)+","+str(self.meter)+","+str(self.sample_type)+","+str(self.sample_set)+","+str(self.volume)+","+str(self.inherited)+","+str(self.kiai)

   def is_bpm_change(self):
      return self.inherited
      
   def offset_time(self,time):
      self.t += time

   def offset_slider_v(self, slider_multiplier1, slider_multiplier2):
      """
        slider_multiplier1: slider_multiplier of beatmap
        slider_multiplier2: slider_multiplier to be converted to
      """
      # need to figure out how this conversion will work
      if not self.is_bpm_change():
         self.mspb = slider_multiplier2*self.mspb/slider_multiplier1


class Hit_Object(object):
   def __init__(self, ho_line):
      line = ho_line.split(",")
      self.x = int(line[0])
      self.y = int(line[1])
      self.t = int(line[2])
      self.type = int(line[3])
      self.hitsound = int(line[4])
      
      self.misc = [line[i] for i in range(5,len(line))]
      # self.misc indexes
      #   sliders
      #      0 - slider points
      #      1 - number of repeats
      #      2 - slider travel distance
      #   spinners 
      #      0 - end time of spinner
   
   def get_line(self):
      misc = ""
      for i in range(len(self.misc)):
         misc += str(self.misc[i])
         if i < len(self.misc)-1:
            misc += ","
      return str(self.x)+","+str(self.y)+","+str(self.t)+","+str(self.type)+","+str(self.hitsound)+","+misc
      
   def get_type(self):
      if self.type & 1 == 1:
         return "circle"
      elif self.type & 2 == 2:
         return "slider"
      elif self.type & 8 == 8:
         return "spinner"
   
   def get_end_time(self, mspb=0, sv=0, sm=1):
      if self.get_type() == "circle":
         return self.t
      elif self.get_type() == "spinner":
         return int(self.misc[0])
      else:
         t = float(self.t)
         d = float(self.misc[2])
         repeats = float(self.misc[1])
         return int(round(t+mspb*d*repeats*sv/(-10000*sm)))
   
   def offset_time(self, time):
      self.t += time
      if self.get_type() == "spinner":
         self.misc[0] = int(self.misc[0])+time
   
   
class Beatmap(object):
   def __init__(self, path, beatmap_section):
      # beatmap_section is the result of copying a highlighted section of hit
      # objects in the beatmap editor to the clipboard
      self.stack_leniency = 0
      self.diff_approach = 9
      self.diff_overall = 8
      self.diff_size = 4
      self.diff_drain = 6
      self.slider_multiplier = 1.4
      self.slider_tick = 1
      self.audio = ""
      self.bg = ""
      
      self.timing_points = []
      self.hit_objects = []
      self.break_periods = []
      
      header = 0
      with open(path,"r") as f:
         lines = f.read().split("\n")
         
      def get_number(line):
         return float(re.search("[\d\.-]+$", line).group(0))
         
      # beatmap section ---> 00:00:00 (1,2,3,4,1,2,3,1,1,1,1,....n) -
      bs = beatmap_section.split(" ")
      # time of the start of the beatmap section
      self.t = sum([int(i)*constant for i,constant in zip(bs[0].split(":"),[60000,1000,1])])
      # number of hit objects in the beatmap section
      ho_count = len(bs[1].split(","))
      
      first_bpm = None
      first_sv = None
      
      # collect information from .osu   
      for line in lines:
         if "AudioFilename" in line:
            self.audio = re.search("((?!:).)+.mp3$",line).group(0).strip()
         elif "StackLeniency" in line:
            self.stack_leniency = get_number(line)
         elif "HPDrainRate" in line:
            self.diff_drain = get_number(line)
         elif "CircleSize" in line:
            self.diff_size = get_number(line)
         elif "OverallDifficulty" in line:
            self.diff_overall = get_number(line)
         elif "ApproachRate" in line:
            self.diff_approach = get_number(line)
         elif "SliderMultiplier" in line:
            self.slider_multiplier = get_number(line)
         elif "SliderTickRate" in line:
            self.slider_tick = get_number(line)
         elif line in ["[Events]","[TimingPoints]", "[HitObjects]"]:
            header += 1
         elif header == 1:
            try:
               if line[0] == "0":
                  self.bg = re.findall('"(.*)"',line)[0]
               elif line[0] == "2":
                  bp = Break_Period(line)
                  if bp.start_time >= self.t:
                     self.break_periods.append(bp)
            except:
               pass
         elif header == 2: # timing points
            try:
               tp = Timing_Point(line)
               if tp.is_bpm_change() or tp.is_bpm_change() and tp.t < self.t:
                  first_bpm = tp
               elif not tp.is_bpm_change() and tp.t < self.t:
                  first_sv = tp
               if tp.t >= self.t:
                  if tp.is_bpm_change():
                     sv_tp = Timing_Point(line)
                     sv_tp.mspb = -100
                     sv_tp.inherited = 0
                     self.timing_points.append(sv_tp)
                  elif len(self.timing_points) > 0 and not self.timing_points[-1].is_bpm_change() and self.timing_points[-1].t == tp.t:
                     del self.timing_points[-1]
                  self.timing_points.append(tp)
            except:
               pass
         elif header == 3: # hit objects
            try:
               tp = Hit_Object(line)
               if tp.t >= self.t:
                  if ho_count > 0:
                     self.hit_objects.append(tp)
                     ho_count -= 1
            except:
               pass
      
      # remove the timing points not contained in the beatmap section
      end_time = self.hit_objects[-1].t
      for i in range(len(self.timing_points)):
         if self.timing_points[i].t > end_time:
            self.timing_points[:] = self.timing_points[:i]
            break
      
      # insert the initial slider velocity and bpm timing points        
      first_bpm.t = self.t-5
      self.timing_points.insert(0,first_bpm)
      if first_sv == None:
         sv_tp = Timing_Point(first_bpm.get_line())
         sv_tp.mspb = -100
         sv_tp.inherited = 0
         self.timing_points.insert(1,sv_tp)
      else:
         first_sv.t = self.t
         self.timing_points.insert(1,first_sv)   

break_period_index = None
timing_point_index = None
hit_object_index = None
default_sm = None

settings = {
   "ffmpeg":"",
   "title": "",
   "artist": "",
   "creator": "",
   "version": "",
   "ar":"",
   "od":"",
   "cs":"",
   "hp":"",
   "break":"6000"
}

beatmap_files = []
beatmap_sections = []

# read from settings.txt and append contents to beatmap file paths and beatmap sections
with open("settings.txt","r") as f:
   lines = f.read().split("\n")
   header = 0
   for line in lines:
      if "#" in line or line == "":
         continue
      elif line in ["[Settings]","[osu!Files]", "[BeatmapSections]"]:
         header += 1  
      elif header == 1:
         try:
            settings[re.search("((?!=).)+",line).group(0)] = re.search("((?!=).)+$",line).group(0).strip()
         except:
            pass
      elif header == 2:
         try:
            if line[0] == "*":
               beatmap_files.append(beatmap_files[-1])
            else:
               beatmap_files.append(line)
         except:
            pass
      elif header == 3: 
         try:
            if line[0] == "*":
               beatmap_sections.append(beatmap_sections[-1])
            else:
               beatmap_sections.append(line)
         except:
            pass
         

settings["break"] = abs(int(settings["break"]))
bg = None

AudioSegment.converter = settings["ffmpeg"]
audio = AudioSegment.silent(duration=0)
section_start = settings["break"]/2
section_end = None

with open("beatmap_template.osu") as f:         
   beatmap_template = f.read().split("\n")

# inserts values into beatmap_template and gets the indexes for the break periods, timing poings, and hit objects
for i in range(len(beatmap_template)):
   if "Title" in beatmap_template[i]:
      beatmap_template[i] += settings["title"]
   elif "Artist" in beatmap_template[i]:
      beatmap_template[i] += settings["artist"]
   elif "Creator" in beatmap_template[i]:
      beatmap_template[i] += settings["creator"]
   elif "Version" in beatmap_template[i]:
      beatmap_template[i] += settings["version"]
   elif "HPDrainRate:" in beatmap_template[i]:
      beatmap_template[i] += settings["hp"]
   elif "CircleSize" in beatmap_template[i]:
      beatmap_template[i] += settings["cs"]
   elif "OverallDifficulty" in beatmap_template[i]:
      beatmap_template[i] += settings["od"]
   elif "ApproachRate" in beatmap_template[i]:
      beatmap_template[i] += settings["ar"]
   elif "[Events]" == beatmap_template[i]:
      break_period_index = i+1
   elif "[TimingPoints]" == beatmap_template[i]:
      timing_point_index = i+1
   elif "[HitObjects]" == beatmap_template[i]:
      hit_object_index = i+1
   elif "SliderMultiplier" in beatmap_template[i]:
      default_sm = float(re.search("[\d\.-]+$", beatmap_template[i]).group(0))

# inserts contents into the appropriate line in the beatmap_template by type
def template_insert(type,contents):
   global break_period_index
   global timing_point_index
   global hit_object_index
   global beatmap_template
   
   if type == 0:
      index = break_period_index
   elif type == 1:
      index = timing_point_index
   elif type == 2:
      index = hit_object_index

   beatmap_template.insert(index,contents)
   if type <= 0:
      break_period_index += 1
   if type <= 1:
      timing_point_index += 1
   if type <= 2:
      hit_object_index += 1

for i in range(len(beatmap_files)):
   beatmap = Beatmap(beatmap_files[i],beatmap_sections[i])
   
   # get the first bg path
   if bg == None and beatmap.bg != "":
      bg = os.path.dirname(beatmap_files[i])+os.sep+beatmap.bg
      template_insert(0,"0,0,\""+beatmap.bg+"\"")
      
   # add break periods
   if not section_end == None:
      template_insert(0,"2,"+str(section_end+1)+","+str(section_start-1))

   # create the mp3
   mp3 = AudioSegment.from_mp3(os.path.dirname(beatmap_files[i])+os.sep+beatmap.audio)

   if beatmap.hit_objects[-1].get_type() == "slider":
      last_mspb = None
      last_sv = None
      for tp in reversed(beatmap.timing_points):
         if last_mspb and last_sv:
            break
         elif last_mspb == None and tp.is_bpm_change():
            last_mspb = tp.mspb
         elif last_sv == None and not tp.is_bpm_change():
            last_sv = tp.mspb
      section_end = beatmap.hit_objects[-1].get_end_time(last_mspb,last_sv,beatmap.slider_multiplier)
   else:
      section_end = beatmap.hit_objects[-1].get_end_time()

   start_mp3 = beatmap.t-settings["break"]/2 if beatmap.t-settings["break"]/2 > 0 else 0
   end_mp3 = section_end+settings["break"]/2 if section_end+settings["break"]/2 < len(mp3) else len(mp3)
   
   start_silence = AudioSegment.silent(duration=-beatmap.t+settings["break"]/2) if -beatmap.t+settings["break"]/2 >= 0 else 0
   end_silence = AudioSegment.silent(duration=section_end+settings["break"]/2-len(mp3)) if section_end+settings["break"]/2-len(mp3) >= 0 else 0
   
   mp3 = mp3[start_mp3:end_mp3]
   
   audio += start_silence+mp3+end_silence

   # offset timing points and hit objects
   offset = section_start-beatmap.hit_objects[0].t
   section_end += offset

   for bp in beatmap.break_periods:
      if bp.end_time < beatmap.hit_objects[-1].t:
         bp.offset_time(offset)
         template_insert(0,bp.get_line())

   for tp in beatmap.timing_points:
      tp.offset_time(offset)
      tp.offset_slider_v(beatmap.slider_multiplier,default_sm)
      template_insert(1,tp.get_line())
      
   for ho in beatmap.hit_objects:
      ho.offset_time(offset)
      template_insert(2,ho.get_line())

   section_start += settings["break"]+(section_end-beatmap.hit_objects[0].t)


# the mp3
audio.export("audio.mp3",format="mp3",bitrate="192k")

# the beatmap file
beatmap_file = "%s - %s (%s) [%s].osu" % (settings["artist"],settings["title"],settings["creator"],settings["version"])
with open(beatmap_file,"w") as f:
   for i in beatmap_template:
      f.write(i)
      f.write("\n")

# add files to .osz
osz = "%s - %s.osz" % (settings["artist"],settings["title"])
with ZipFile(osz,"w") as z:
   z.write("audio.mp3")
   z.write(beatmap_file)
   z.write(bg, os.path.basename(bg))

os.remove(beatmap_file)
os.remove("audio.mp3")