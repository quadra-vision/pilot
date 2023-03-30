#!/usr/bin/env python3
import os
import sys
import bz2
import urllib.parse
import capnp
import warnings
import math

from tqdm import tqdm

from prettytable import PrettyTable

from cereal import log as capnp_log
from tools.lib.filereader import FileReader

class LogReader:
  def __init__(self, fn, canonicalize=True, only_union_types=False, sort_by_time=False, dat=None):
    self.data_version = None
    self._only_union_types = only_union_types

    ext = None
    if not dat:
      _, ext = os.path.splitext(urllib.parse.urlparse(fn).path)
      if ext not in ('', '.bz2'):
        # old rlogs weren't bz2 compressed
        raise Exception(f"unknown extension {ext}")

      with FileReader(fn) as f:
        dat = f.read()

    if ext == ".bz2" or dat.startswith(b'BZh9'):
      dat = bz2.decompress(dat)

    ents = capnp_log.Event.read_multiple_bytes(dat)

    _ents = []
    try:
      for e in ents:
        _ents.append(e)
    except capnp.KjException:
      warnings.warn("Corrupted events detected", RuntimeWarning)

    self._ents = list(sorted(_ents, key=lambda x: x.logMonoTime) if sort_by_time else _ents)
    self._ts = [x.logMonoTime for x in self._ents]

  @classmethod
  def from_bytes(cls, dat):
    return cls("", dat=dat)

  def print_immediate_disable_events(self):
     for ent in self._ents:
      if ent.which() == 'carEvents':
        car_event = ent.carEvents
        for event in car_event:
          if event.immediateDisable:
            print(event.name)

  def immediate_disables_table(self):
    events = []
    for ent in self._ents:
        if ent.which() == 'carEvents':
            car_event = ent.carEvents
            for event in car_event:
                if event.immediateDisable:
                    name = str(event.name)
                    found = False
                    for e in events:
                        if e['event'] == name:
                            e['count'] += 1
                            found = True
                            break
                    if not found:
                        events.append({
                            'event': name,
                            'count': 1
                        })

   
    return events

  def get_segments_hours_engaged_hours(self, count_segments):
    # Adding driving hours
    hours_driving = count_segments / 60 # division by 60 is done to convert minutes to hours

    #engaged_hours = math.floor(count_segments * int(lr.pct_engagement()))

    minutes = count_segments * int(lr.pct_engagement())
    hours = math.floor(minutes / 100)

    engaged_hours = hours / 60

    # Immediate disables table
    immediate_table = PrettyTable(['', 'segments', 'hours', 'engaged hours', 'engagement percentage'])

    immediate_table.add_row(['Quadra.', count_segments, round(hours_driving, 2), engaged_hours, '%d%%' % int(lr.pct_engagement())])

    immediate_table.title = 'MTBF analysis for Quadra.'

    print(immediate_table)

  def soft_disables_table(self):
    events = []
    for ent in self._ents:
        if ent.which() == 'carEvents':
            car_event = ent.carEvents
            for event in car_event:
                if event.softDisable:
                    name = str(event.name)
                    found = False
                    for e in events:
                        if e['event'] == name:
                            e['count'] += 1
                            found = True
                            break
                    if not found:
                        events.append({
                            'event': name,
                            'count': 1
                        })
    
    return events
  
  def pct_engagement(self):
    engagement = []

    for ent in self._ents:
       if ent.which() == 'controlsState':
          car_state = ent.controlsState.engageable
          engagement.append(car_state)
    
    count_engagement = sum(1 for x in engagement if x)

    pct_engagement = (count_engagement / len(engagement)) * 100

    return pct_engagement   
  
  def sum_events(self, events):
    if not events:
        return {}

    result = {}
    for event_list in events:
        for event_dict in event_list:
            event = event_dict['event']
            count = event_dict['count']
            if event in result:
                result[event] += count
            else:
                result[event] = count
    return [{'event': event, 'count': count} for event, count in result.items()]

  def print_table_disables(self, events_sanitized, title):
      immediate_table = PrettyTable(['', 'event', 'MTBF', 'count'])
      
      for i, event in enumerate(events_sanitized):
        immediate_table.add_row([i, event['event'], 'MTBF', event['count']])

      immediate_table.align["event"] = "l"
      immediate_table.align["count"] = "r"

      immediate_table.title = title

      print(immediate_table)

  def __iter__(self):
    for ent in self._ents:
      if self._only_union_types:
        try:
          ent.which()
          yield ent
        except capnp.lib.capnp.KjException:
          pass
      else:
        yield ent

if __name__ == "__main__":
  import codecs
  # capnproto <= 0.8.0 throws errors converting byte data to string
  # below line catches those errors and replaces the bytes with \x__
  codecs.register_error("strict", codecs.backslashreplace_errors)

  # initialize count to 0
  count_segments = 0
  all_events_soft_disables = []
  all_events_immediate_disables = []
  
  # iterate through all the subdirectories 
  log_path = sys.argv[1]

  # iterate through all the subdirectories of "arquivos"
  for i, subdir in enumerate(tqdm(os.listdir(log_path))):
    #if i >= 80:
       #break
    subdir_path = os.path.join(log_path, subdir)

    # check if the current path is a directory
    if os.path.isdir(subdir_path):
      count_segments += 1

    # check if the subdirectory is a directory (ignore files)
    if os.path.isdir(subdir_path):

      # iterate through all the files in the subdirectory
      for file in os.listdir(subdir_path):
        file_path = os.path.join(subdir_path, file)

        # process the log file
        lr = LogReader(file_path, sort_by_time=True)

        events_soft_disables = lr.soft_disables_table()
        all_events_soft_disables.append(events_soft_disables)

        events_immediate_disables = lr.immediate_disables_table()
        all_events_immediate_disables.append(events_immediate_disables)
        
  lr.get_segments_hours_engaged_hours(count_segments)

  events_sanitized = lr.sum_events(all_events_immediate_disables)
   # Immediate disables table
  lr.print_table_disables(events_sanitized, 'Immediate disables')

  events_sanitized = lr.sum_events(all_events_soft_disables)
  # Soft disables table
  lr.print_table_disables(events_sanitized, 'Soft disables')

        


