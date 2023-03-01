#!/usr/bin/env python3
import os
import sys
import bz2
import urllib.parse
import capnp
import warnings

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
    
    # Immediate disables table
    immediate_table = PrettyTable(['', 'event', 'count'])
    for i, event in enumerate(events):
      immediate_table.add_row([i, event['event'], event['count']])

    immediate_table.align["event"] = "l"
    immediate_table.align["count"] = "r"

    immediate_table.title = 'Immediate disables'

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
    
    # Soft disables table
    immediate_table = PrettyTable(['', 'event', 'count'])
    for i, event in enumerate(events):
      immediate_table.add_row([i, event['event'], event['count']])

    immediate_table.align["event"] = "l"
    immediate_table.align["count"] = "r"

    immediate_table.title = 'Soft disables'

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
  log_path = sys.argv[1]
  lr = LogReader(log_path, sort_by_time=True)
  lr.immediate_disables_table()
  lr.soft_disables_table()
  #for msg in lr:
    #print(msg)

