#!/usr/bin/env python3
import sys

sys.modules['_elementtree'] = None

import xml.etree.ElementTree as ET
import re
import os
import argparse
from urllib.parse import urlparse

blacklistedChars: list = ["<", ">", "&", "\"", "'"]
bloatTags: list = ["DateInstalled", "Networking", "Data", "Environment"]
noticeTags: list = ["Category", "Registry", "Icon"]
userInputTags: list = ["Description", "Overview", "Config", "Changelog"]

class LineNumberingParser(ET.XMLParser): # https://stackoverflow.com/a/36430270
  def _start_list(self, *args, **kwargs):
    # Here we assume the default XML parser which is expat
    # and copy its element position attributes into output Elements
    element = super(self.__class__, self)._start_list(*args, **kwargs)
    element._start_line_number = self.parser.CurrentLineNumber
    element._start_column_number = self.parser.CurrentColumnNumber
    element._start_byte_index = self.parser.CurrentByteIndex
    return element

  def _end(self, *args, **kwargs):
    element = super(self.__class__, self)._end(*args, **kwargs)
    element._end_line_number = self.parser.CurrentLineNumber
    element._end_column_number = self.parser.CurrentColumnNumber
    element._end_byte_index = self.parser.CurrentByteIndex
    return element

def check_xml(filename: str):
  webUiPort: dict = { "port": None, "line": None }
  targetPorts: list = []
  requiredLinks: bool = False

  try:
    tree = ET.parse(filename, parser=LineNumberingParser())
  except ET.ParseError as e:
    title = "XML Parse Error"
    message = f"Failed to parse XML: {str(e)}"
    # Extract line number if available from the error message
    line_match = re.search(r'line (\d+)', str(e))
    if line_match:
      line = line_match.group(1)
      print(f"::error file={filename},line={line},title={title}::{message}")
    else:
      print(f"::error file={filename},title={title}::{message}")
    return  # Exit the function early since we can't continue without a valid tree

  root = tree.getroot()

  # Errors

  for tag in ["Support", "Project"]:
    if (tag := root.find(tag)) is not None:
      if len(tag.text) != 0:
        if not (tag.text.startswith(" ") or tag.text.endswith(" ")):
          requiredLinks = True
          break

  if not requiredLinks:
    title = "Missing Support or Project Link"
    message = "No Support or Project Link Present"
    print(f"::error file={filename},title={title}::{message}")

  for overview in root.iter('Overview'):
    if "Converted By Community Applications" in overview.text:
      title = "Converted By Community Applications"
      message = "Blacklisted: Obvious CA conversion templates are disallowed"
      line = overview._end_line_number
      print(f"::error file={filename},line={line},title={title}::{message}")

  for tag in userInputTags:
    for element in root.iter(tag):
      texts = [element.text, element.attrib.get("Default"), element.attrib.get("Description")]
      if any(char in texts for char in blacklistedChars):
        title = f"Blacklisted Character"
        message = f"Blacklisted Character in {tag}"
        line = element._end_line_number
        print(f"::error file={filename},line={line},title={title}::{message}")

  for tag in bloatTags:
    if root.find(tag) is not None:
      title = f"Unnecessary Tag"
      message = f"Unnecessary {tag} Tag Present"
      print(f"::error file={filename},title={title}::{message}")

  # Notices

  if (postArg := root.find("PostArgs")) is not None:
    if postArg.text:
      if len(postArg) != 0:
        title = "PostArgs Present"
        message = "PostArgs are to be used with care"
        print(f"::notice file={filename},title={title}::{message}")

  for tag in noticeTags:
    if root.find(tag) is None:
      title = f"Missing Tag"
      message = f"No {tag} entry present."
      print(f"::notice file={filename},title={title}::{message}")

  # Webport logic

  for web in root.iter('WebUI'):
      if not web.text:
          continue
      ex = re.search(r"\[PORT:(\d+)\]", web.text, re.IGNORECASE)
      if ex:
          webUiPort["port"] = ex.group(1)
          webUiPort["line"] = web._end_line_number

  for config in root.iter('Config'):
      if config.attrib.get("Type") == "Port":
          targetPorts.append(config.attrib.get("Target"))

  if webUiPort.get("port"):
      if webUiPort.get("port") not in targetPorts:
          title = "WebUI Port not in Config"
          message = f"WebUI Port {webUiPort.get('port')} is not a target in Config"
          line = webUiPort.get("line")
          print(f"::error file={filename},line={line},title={title}::{message}")

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Template Checker")
  parser.add_argument('-f', '--files', nargs='+', help="Runs only on file")

  args = parser.parse_args()

  if args.files:
    _files: list = []
    for fileargs in args.files:
      if os.path.isfile(fileargs):
        _files.append(fileargs)
      else:
        print(f"{fileargs} is not a file")
    if len(_files) != 0:
      [check_xml(filename = file) for file in _files]
    else:
      print("No files found")

  else:
    directory = "templates"
    for filename in os.scandir(directory):
      if filename.name.endswith(".xml") and filename.is_file():
          if filename.name.endswith("ca_profile.xml"):
            continue
          check_xml(filename = filename.path)
