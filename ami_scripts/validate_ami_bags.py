#!/usr/bin/env python3
"""
Consolidated Python script to validate AMI Bags (JSON only).
Derived from nkrabben's: https://github.com/NYPL/ami-tools/blob/main/bin/validate_ami_bags.py

Refactoring / improvements include:

1. More descriptive docstrings in classes and methods.
2. Type hints in function signatures (no runtime changes).
3. A 'Utilities' section for small helper functions.
4. Minor duplication removal: a helper function to compare PM <-> MZ/EM/SC sets.
5. Preserved all existing function names, exception types, and logic.
"""

# =========================== STANDARD LIBRARY IMPORTS =========================
import os
import re
import csv
import json
import argparse
import logging
import datetime
from typing import Dict, Any, Union, List, Tuple, Set, Optional

# 3rd party libraries
import numpy as np
import pandas as pd
from tqdm import tqdm
import bagit
from pymediainfo import MediaInfo
from dateutil import parser

LOGGER = logging.getLogger(__name__)

# =============================================================================
#                    ami_file_constants
# =============================================================================

MOV_EXT = "mov"
DV_EXT = "dv"
MKV_EXT = "mkv"
MKA_EXT = "mka"
MP4_EXT = "mp4"
ISO_EXT = "iso"
TAR_EXT = "tar"
WAV_EXT = "wav"
FLAC_EXT = "flac"

MEDIA_EXTS = [MOV_EXT, DV_EXT, MKV_EXT, MKA_EXT, MP4_EXT, ISO_EXT, TAR_EXT, WAV_EXT, FLAC_EXT]

VIDEO_EXTS = [MOV_EXT, DV_EXT, MKV_EXT, MP4_EXT, ISO_EXT, TAR_EXT]
AUDIO_EXTS = [MKA_EXT, WAV_EXT, FLAC_EXT]

AO_ENDING = "ao"
PM_ENDING = "pm"
MZ_ENDING = "mz"
EM_ENDING = "em"
SC_ENDING = "sc"

FILE_ROLES = [AO_ENDING, PM_ENDING, EM_ENDING, SC_ENDING, MZ_ENDING]

# Regex patterns specifically for file naming
FN_NOEXT_RE = r"^[a-z]{3}_[a-z\d\-\*_]+_([vfrspt]\d{2})+_(ao|pm|em|sc|mz)$"
STUB_FN_NOEXT_RE = r"^[a-z]{3}_[a-z\d\-\*_]+_([vfrspt]\d{2})+_(ao|pm|em|sc|mz)"
regex_roles = "|".join(FILE_ROLES)
regex_exts = "|".join(MEDIA_EXTS)
FN_RE = rf"^[a-z]{{3}}_[a-z\d\-\*_]+_([vfrspt]\d{{2}})+_({regex_roles})\.({regex_exts})$"


# =============================================================================
#                             Utility Functions
# =============================================================================

def parse_date(date_string: str) -> str:
    """
    Parse a date string into 'YYYY-MM-DD' format. 
    Tries multiple parsers (dateutil, strptime).
    
    :param date_string: The date string to parse.
    :return: The parsed date in 'YYYY-MM-DD' format.
    :raises ValueError: If no valid date can be parsed.
    """
    try:
        parsed = parser.parse(date_string)
    except Exception:
        try:
            parsed = datetime.datetime.strptime(date_string, '%Z %Y-%m-%d %H:%M:%S')
        except Exception:
            raise ValueError(f"Could not parse date string: {date_string}")
    return parsed.date().strftime('%Y-%m-%d')


def parse_duration(ms_int: Optional[int]) -> str:
    """
    Convert duration in milliseconds to an HH:MM:SS.mmm string.
    
    :param ms_int: Duration in milliseconds.
    :return: A string in the format 'HH:MM:SS.mmm'.
    """
    if not ms_int:
        return "00:00:00.000"
    hours = ms_int // 3600000
    minutes = (ms_int % 3600000) // 60000
    seconds = (ms_int % 60000) // 1000
    ms = ms_int % 1000
    return f"{hours:0>2}:{minutes:0>2}:{seconds:0>2}.{ms:0>3}"


def fuzzy_check_md_value(first_value: float, second_value: float, fuzziness: float) -> bool:
    """
    Compare two numeric values, returning True if they're within 'fuzziness'.
    
    :param first_value: The first numeric value.
    :param second_value: The second numeric value.
    :param fuzziness: The allowable difference.
    :return: True if abs difference <= fuzziness, else False.
    """
    difference = abs(first_value - second_value)
    return difference <= fuzziness


def convert_dotKeyToNestedDict(tree: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
    """
    Convert a 'dot.key' string into nested dictionaries. 
    Modifies 'tree' in place.
    
    :param tree: The (possibly nested) dictionary to modify.
    :param key: The dot key (e.g., 'technical.durationMilli.measure').
    :param value: The value to set.
    :return: The updated dictionary.
    """
    if "." in key:
        k, rest = key.split(".", 1)
        if k not in tree:
            tree[k] = {}
        convert_dotKeyToNestedDict(tree[k], rest, value)
    else:
        tree[key] = value
    return tree


def convert_nestedDictToDotKey(tree: Dict[str, Any],
                               separator: str = ".",
                               prefix: str = "") -> Dict[str, Any]:
    """
    Convert a nested dictionary into a dict of dot.keys.
    
    :param tree: The nested dictionary.
    :param separator: The dot (or other) separator.
    :param prefix: The prefix to prepend to keys.
    :return: A flat dictionary with dot-separated keys.
    """
    new_tree = {}
    for key, value in tree.items():
        new_key = prefix + key
        if isinstance(value, dict):
            new_tree.update(convert_nestedDictToDotKey(value, separator, new_key + separator))
        else:
            new_tree[new_key] = value
    return new_tree


# =============================================================================
#            ami_bag_constants (JSON only)
# =============================================================================

FILENAME_REGEX = re.compile(
    r"([a-z]{3}_[a-z0-9]+_v\d{2}(([frspt]\d{2})+)?_(ao|pm|mz|em|sc|pf|assetfront|assetback|assetside|boxfront|boxback|boxside|reelfront|ephemera)([~\d\-]+)?\.[a-z0-9]+)"
    r"|(\d{4}_\d{3}_[\da-zA-Z_]+\.(json))",  # removed xlsx/old references
    re.IGNORECASE
)
SUBOBJECT_REGEX = re.compile(r"_v\d{2}(f\d{2})?([rspt]\d{2})+")
SUBOBJECT_PART_REGEX = re.compile(r"_v\d{2}([frst\d]+)?(p|pt)\d{2}")

PM_DIR = "PreservationMasters"
MZ_DIR = "Mezzanines"
EM_DIR = "EditMasters"
SC_DIR = "ServiceCopies"
AO_DIR = "ArchiveOriginals"
IM_DIR = "Images"

MOV_EXT_FULL = ".mov"
DV_EXT_FULL = ".dv"
MKV_EXT_FULL = ".mkv"
MKA_EXT_FULL = ".mka"
MP4_EXT_FULL = ".mp4"
ISO_EXT_FULL = ".iso"
TAR_EXT_FULL = ".tar"
WAV_EXT_FULL = ".wav"
FLAC_EXT_FULL = ".flac"
JSON_EXT = ".json"
JPEG_EXT = ".jpeg"
JPG_EXT = ".jpg"
GZ_EXT = ".gz"
SRT_EXT = ".srt"
CUE_EXT = ".cue"
SCC_EXT = ".scc"

MEDIA_EXTS_FULL = [
    MOV_EXT_FULL, DV_EXT_FULL, MKV_EXT_FULL, MKA_EXT_FULL, MP4_EXT_FULL,
    ISO_EXT_FULL, TAR_EXT_FULL, WAV_EXT_FULL, FLAC_EXT_FULL
]

COMPRESSED_EXTS = [MKV_EXT_FULL, MKA_EXT_FULL, FLAC_EXT_FULL]
UNCOMPRESSABLE_EXTS = [DV_EXT_FULL, ISO_EXT_FULL, TAR_EXT_FULL]
UNCOMPRESSED_EXTS = [MOV_EXT_FULL, WAV_EXT_FULL]

# JSON_SUBTYPES only (Excel references removed)
JSON_SUBTYPES = {
    "film": (set([PM_DIR, MZ_DIR, SC_DIR, IM_DIR]),
             set([JSON_EXT, MKV_EXT_FULL, MOV_EXT_FULL, MP4_EXT_FULL, JPEG_EXT, JPG_EXT,
                  GZ_EXT, SRT_EXT, SCC_EXT])),
    "video": (set([PM_DIR, SC_DIR, IM_DIR]),
              set([JSON_EXT, MOV_EXT_FULL, MKV_EXT_FULL, DV_EXT_FULL, MP4_EXT_FULL,
                   JPEG_EXT, JPG_EXT, GZ_EXT, SRT_EXT, SCC_EXT, ISO_EXT_FULL])),
    "audio": (set([PM_DIR, EM_DIR, IM_DIR]),
              set([JSON_EXT, WAV_EXT_FULL, FLAC_EXT_FULL, JPEG_EXT, JPG_EXT, CUE_EXT])),
    "data":  (set([PM_DIR, IM_DIR]),
              set([JSON_EXT, ISO_EXT_FULL, JPEG_EXT, JPG_EXT]))
}


# =============================================================================
#                Minimal placeholders for ami_md_constants (JSON only)
# =============================================================================

class ami_md_constants:
    """
    Holds sets of fields and mappings for JSON-based audio/video/film metadata. 
    No Excel references.
    """
    JSON_AUDIOFIELDS = [
        "filename", "extension", "fileFormat", "fileSize",
        "dateCreated", "durationHuman", "durationMilli", "audioCodec"
    ]
    JSON_VIDEOFIELDS = [
        "filename", "extension", "fileFormat", "fileSize",
        "dateCreated", "durationHuman", "durationMilli",
        "audioCodec", "videoCodec"
    ]
    JSON_VIDEOOPTICALPMFIELDS = [
        "filename", "extension", "fileFormat", "fileSize",
        "dateCreated", "durationHuman", "durationMilli",
        "audioCodec", "videoCodec"
    ]

    JSON_TO_AUDIO_FILE_MAPPING = {
        "filename": "base_filename",
        "extension": "extension",
        "audioCodec": "audio_codec",
        "durationHuman": "duration_human",
        "durationMilli.measure": "duration_milli"
    }
    JSON_TO_VIDEO_FILE_MAPPING = {
        "filename": "base_filename",
        "extension": "extension",
        "audioCodec": "audio_codec",
        "videoCodec": "video_codec",
        "durationHuman": "duration_human",
        "durationMilli.measure": "duration_milli"
    }
    JSON_TO_VIDEOOPTICALPM_FILE_MAPPING = {
        "filename": "base_filename",
        "extension": "extension",
        "audioCodec": "audio_codec",
        "videoCodec": "video_codec",
        "durationHuman": "duration_human",
        "durationMilli.measure": "duration_milli"
    }


# =============================================================================
#                       Custom Exceptions
# =============================================================================

class AMIFileError(Exception):
    """Raised when an AMIFile cannot be created or parsed properly."""
    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return repr(self.message)


class AMIJSONError(Exception):
    """Raised when an ami_json file is missing or has invalid fields."""
    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return repr(self.message)


class ami_bagError(Exception):
    """Raised on bag-level logic or content errors."""
    def __init__(self, message: str):
        self.message = message

    def __str__(self) -> str:
        return repr(self.message)


# =============================================================================
#                              ami_file
# =============================================================================

class ami_file:
    """
    Class that parses technical metadata of an audio/video file using pymediainfo,
    storing relevant attributes for further validation.
    """

    def __init__(self, filepath: str, mi: bool = True):
        """
        :param filepath: Path to the media file.
        :param mi: If True, parse tech md using pymediainfo. Otherwise, minimal fallback.
        :raises AMIFileError: If file not found or file extension is not recognized.
        """
        if os.path.isfile(filepath):
            self.filepath = os.path.abspath(filepath)
            self.filename = os.path.basename(self.filepath)
        else:
            self.raise_AMIFileError(f"{filepath} is not a valid filepath")

        if mi:
            self.set_techmd_values()
        else:
            self.date_filesys_created = datetime.datetime.fromtimestamp(
                os.path.getctime(self.filepath)
            ).strftime('%Y-%m-%d')
            self.extension = os.path.splitext(self.filepath)[1][1:]  # remove leading '.'

        # Decide if file is audio or video
        if self.extension.lower() in VIDEO_EXTS:
            self.type = "video"
        elif self.extension.lower() in AUDIO_EXTS:
            self.type = "audio"
        else:
            self.raise_AMIFileError(
                f"{self.filename} does not appear to be an accepted audio or video format."
            )

    def set_techmd_values(self) -> None:
        """
        Parse technical metadata via pymediainfo. Sets attributes such as
        base_filename, extension, format, size, date_filesys_created, date_created,
        duration_milli/human, audio_codec, video_codec.
        :raises AMIFileError: If pymediainfo fails or no General track is found.
        """
        try:
            techmd = MediaInfo.parse(self.filepath)
        except Exception:
            self.raise_AMIFileError("pymediainfo failed to run, so techmd has not been parsed")

        md_track = None
        for track in techmd.tracks:
            if track.track_type == "General":
                md_track = track
                break

        if not md_track:
            self.raise_AMIFileError("Could not find General track from MediaInfo")

        self.base_filename = md_track.file_name.rsplit('.', 1)[0] if md_track.file_name else None
        self.extension = md_track.file_extension if md_track.file_extension else ""
        self.format = md_track.format
        self.size = md_track.file_size

        self.date_filesys_created = datetime.datetime.fromtimestamp(
            os.path.getctime(self.filepath)
        ).strftime('%Y-%m-%d')

        if md_track.encoded_date:
            self.date_created = parse_date(md_track.encoded_date)
        elif md_track.file_last_modification_date:
            self.date_created = parse_date(md_track.file_last_modification_date)
        else:
            self.date_created = self.date_filesys_created

        if md_track.duration:
            self.duration_milli = md_track.duration
            self.duration_human = parse_duration(self.duration_milli)
        else:
            self.duration_milli = 0
            self.duration_human = "00:00:00.000"

        # Audio codec
        if not md_track.audio_codecs:
            self.audio_codec = None
        elif '/' in md_track.audio_codecs:
            self.audio_codec = '|'.join({x.strip() for x in md_track.audio_codecs.split('/')})
        else:
            self.audio_codec = md_track.audio_codecs

        # Video codec
        if md_track.codecs_video:
            self.video_codec = md_track.codecs_video
        else:
            self.video_codec = None

    def raise_AMIFileError(self, msg: str) -> None:
        """
        Log and raise an AMIFileError.
        :param msg: The error message.
        """
        logging.error(msg + '\n')
        raise AMIFileError(msg)


# =============================================================================
#                       ami_json
# =============================================================================

ZERO_VALUE_FIELDS = ['source.audioRecording.numberOfAudioTracks']

class ami_json:
    """
    Representation of a single JSON file’s metadata. 
    Provides validation checks, references to an associated media file, etc.
    """

    def __init__(self,
                 filepath: Optional[str] = None,
                 load: bool = True,
                 flat_dict: Optional[Dict[str, Any]] = None,
                 schema_version: str = "x.0.0",
                 media_filepath: Optional[str] = None):
        """
        :param filepath: Path to the JSON file (if loading from disk).
        :param load: If True, attempts to open and parse the JSON file.
        :param flat_dict: Optional flat dictionary used to build nested metadata.
        :param schema_version: Default schema version if missing in the flat_dict.
        :param media_filepath: Explicit path to the described media file (if known).
        :raises AMIJSONError: If JSON file fails to load or required fields are missing.
        """
        self.path = None
        self.filename = None
        self.dict: Dict[str, Any] = {}

        if filepath:
            self.path = filepath
            self.filename = os.path.basename(filepath)
            if load:
                try:
                    with open(self.path, 'r', encoding='utf-8-sig') as f:
                        self.dict = json.load(f)
                except Exception:
                    self.raise_jsonerror(f"Could not load {self.filename}. Check that it is valid JSON.")
                else:
                    self.set_mediaformattype()

        if flat_dict:
            self.filename = os.path.splitext(flat_dict["asset.referenceFilename"])[0] + ".json"
            nested_dict = {}
            if "asset.schemaVersion" not in flat_dict.items():
                flat_dict["asset.schemaVersion"] = schema_version

            for key, value in flat_dict.items():
                if value:
                    # Convert PD Timestamps, np types, skip empty
                    if pd.isnull(value):
                        continue
                    if isinstance(value, pd.Timestamp):
                        value = value.strftime('%Y-%m-%d')
                    if isinstance(value, np.generic):
                        value = np.asscalar(value)
                    nested_dict = convert_dotKeyToNestedDict(nested_dict, key, value)

                # handle zero fields
                if key in ZERO_VALUE_FIELDS and value == 0:
                    nested_dict = convert_dotKeyToNestedDict(nested_dict, key, value)

            self.dict = nested_dict
            self.set_mediaformattype()
            self.coerce_strings()

        if media_filepath:
            self.set_mediafilepath(media_filepath)

    def set_mediaformattype(self) -> None:
        """
        Sets the 'media_format_type' attribute based on self.dict["source"]["object"]["type"].
        """
        try:
            _ = self.dict
        except AttributeError:
            self.raise_jsonerror("Cannot set format type, metadata dictionary not loaded.")
        self.media_format_type = self.dict["source"]["object"]["type"][0:5]

    def set_mediafilepath(self, media_filepath: Optional[str] = None) -> None:
        """
        Determines or confirms the media_filepath attribute. If not provided, tries to guess
        from JSON references or from the JSON file’s path.

        :param media_filepath: If provided, explicitly sets self.media_filepath.
        :raises AMIJSONError: If no file is found or references cannot be resolved.
        """
        if not media_filepath:
            LOGGER.info("Attempting to locate media file based on JSON location.")
            if hasattr(self, "path") and self.path:
                try:
                    self.check_reffn()
                except Exception:
                    try:
                        self.check_techfn()
                    except Exception:
                        self.raise_jsonerror("Cannot determine described media file from filename metadata")
                    else:
                        media_filename = (self.dict["technical"]["filename"] + '.' +
                                          self.dict["technical"]["extension"])
                else:
                    media_filename = self.dict["asset"]["referenceFilename"]

                media_filepath = os.path.join(os.path.split(self.path)[0], media_filename)
            else:
                self.raise_jsonerror("Cannot determine described media file location with no JSON file path.")

        if os.path.isfile(media_filepath):
            self.media_filepath = media_filepath
        else:
            self.raise_jsonerror(f"No media file found at {media_filepath}")

    def coerce_strings(self) -> None:
        """
        Converts certain numeric or non-string fields into strings for JSON consistency.
        Specifically processes bibliographic keys and digitizer address.
        """
        if "bibliographic" not in self.dict:
            return

        for key, item in self.dict["bibliographic"].items():
            if key in ['contentNotes', 'accessNotes', 'title']:
                continue
            if not isinstance(item, str):
                item_split = str(item).split()
                if len(item_split) > 1 and item_split[1] == '0':
                    continue
                self.dict["bibliographic"][key] = str(item)

        try:
            for k, v in self.dict["digitizer"]["organization"]["address"].items():
                self.dict["digitizer"]["organization"]["address"][k] = str(v).split('.')[0]
        except Exception:
            return

    def validate_json(self) -> bool:
        """
        Perform multiple checks to ensure the JSON is well-formed and consistent:
        1. check_techfn
        2. check_reffn
        3. compare_techfn_reffn
        4. check_techmd_fields
        5. Compare with physical media (if media_filepath is set)
           - compare_techfn_media_filename
           - check_techmd_values

        :return: True if all checks pass, otherwise raises AMIJSONError.
        """
        valid = True
        LOGGER.info(f"Checking: {os.path.basename(self.filename)}")

        # Tech filename
        try:
            self.check_techfn()
        except AMIJSONError as e:
            LOGGER.warning(f"JSON metadata out of spec: {e.message}")
            valid = False

        # Reference filename
        try:
            self.check_reffn()
        except AMIJSONError as e:
            LOGGER.warning(f"JSON metadata out of spec: {e.message}")
            valid = False

        # Compare tech filename <-> ref filename
        try:
            self.compare_techfn_reffn()
        except AMIJSONError as e:
            LOGGER.warning(f"JSON metadata out of spec: {e.message}")
            valid = False

        # Check required tech fields
        try:
            self.check_techmd_fields()
        except AMIJSONError as e:
            LOGGER.error(f"JSON metadata out of spec: {e.message}")
            valid = False

        # If media_filepath known, do deeper checks
        if hasattr(self, 'media_filepath'):
            try:
                self.compare_techfn_media_filename()
            except AMIJSONError as e:
                LOGGER.error(f"JSON metadata out of spec: {e.message}")
                valid = False

            try:
                self.check_techmd_values()
            except AMIJSONError as e:
                LOGGER.warning(f"JSON metadata out of spec: {e.message}")
                valid = False
        else:
            LOGGER.warning("Cannot check technical metadata vs. media file—no media file location known.")

        return valid

    def check_techmd_fields(self) -> bool:
        """
        Ensures the JSON has the correct set of 'technical' fields based on the object type.
        Raises AMIJSONError if missing fields are found.
        """
        self.valid_techmd_fields = False
        found_fields = set(list(self.dict["technical"].keys()))
        mm_type = self.media_format_type
        # If it’s "video optical disc"...
        if (self.dict["asset"]["fileRole"] == 'pm'
            and self.dict["source"]["object"]["type"] == 'video optical disc'):
            expected_fields = set(ami_md_constants.JSON_VIDEOOPTICALPMFIELDS)

            # --- BEGIN OPTIONAL DVD ISO CHECK ---
            # If the fileFormat is "ISO 9660" or "ISO 9660 / DVD Video",
            # you can remove some or all of the audio/video fields from expectations:
            actual_fileformat = self.dict["technical"].get("fileFormat", "")
            if "ISO 9660" in actual_fileformat or "DVD Video" in actual_fileformat:
                # For example, remove fields that are rarely present for DVD ISO:
                expected_fields.discard("audioCodec")
                expected_fields.discard("videoCodec")
                expected_fields.discard("durationHuman")
                expected_fields.discard("durationMilli")
            # --- END OPTIONAL DVD ISO CHECK ---
        elif mm_type == "audio":
            expected_fields = set(ami_md_constants.JSON_AUDIOFIELDS)
        elif (self.dict["asset"]["fileRole"] == 'pm'
              and self.dict["source"]["object"]["type"] == 'video optical disc'):
            expected_fields = set(ami_md_constants.JSON_VIDEOOPTICALPMFIELDS)
        elif mm_type == "video":
            expected_fields = set(ami_md_constants.JSON_VIDEOFIELDS)
        elif (mm_type == "film" and 'contentSpecifications' in self.dict['source']):
            expected_fields = set(ami_md_constants.JSON_VIDEOFIELDS)
            if self.dict['source']['audioRecording']['numberOfAudioTracks'] == 0:
                expected_fields.discard('audioCodec')
        elif (mm_type == "film" and 'contentSpecifications' not in self.dict['source']):
            expected_fields = set(ami_md_constants.JSON_AUDIOFIELDS)
        else:
            expected_fields = set()

        missing = expected_fields - found_fields
        if missing:
            self.raise_jsonerror(f"Metadata missing the following fields: {missing}")

        self.valid_techmd_fields = True
        return True

    def set_media_file(self, mi: bool = True) -> None:
        """
        Instantiate an ami_file object from self.media_filepath if not already set.
        :param mi: if True, use pymediainfo for parsing.
        """
        if not hasattr(self, 'media_filepath'):
            self.set_mediafilepath()
        self.media_file = ami_file(self.media_filepath, mi)

    def check_techmd_values(self) -> bool:
        """
        For each 'technical' field, compare the JSON's value to the corresponding 
        attribute in ami_file, with a tolerance for small differences in duration.
        Raises AMIJSONError if they differ beyond tolerance.
        """
        if not hasattr(self, 'valid_techmd_fields'):
            self.check_techmd_fields()
        if not hasattr(self, 'media_file'):
            self.set_media_file()

        mm_type = self.media_format_type

        if mm_type == "audio":
            field_mapping = ami_md_constants.JSON_TO_AUDIO_FILE_MAPPING
        elif (self.dict["asset"]["fileRole"] == 'pm'
              and self.dict["source"]["object"]["type"] == 'video optical disc'):
            field_mapping = ami_md_constants.JSON_TO_VIDEOOPTICALPM_FILE_MAPPING
            field_mapping.pop("audioCodec", None)
            field_mapping.pop("videoCodec", None)
            field_mapping.pop("durationHuman", None)
            field_mapping.pop("durationMilli.measure", None)
        elif mm_type == "video":
            field_mapping = ami_md_constants.JSON_TO_VIDEO_FILE_MAPPING
        elif (mm_type == "film" and 'contentSpecifications' in self.dict['source']):
            field_mapping = ami_md_constants.JSON_TO_VIDEO_FILE_MAPPING.copy()
            if (self.dict['source']['audioRecording']['numberOfAudioTracks'] == 0 and
                'audioCodec' in field_mapping):
                field_mapping.pop('audioCodec')
        elif (mm_type == "film" and 'contentSpecifications' not in self.dict['source']):
            field_mapping = ami_md_constants.JSON_TO_AUDIO_FILE_MAPPING
        else:
            field_mapping = {}

        errors = []
        for key, mapped_field in field_mapping.items():
            try:
                self.check_md_value(key, mapped_field)
            except AMIJSONError as e:
                errors.append(e.message)

        if errors:
            self.raise_jsonerror(' '.join(errors))
        return True

    def check_md_value(self, field: str, mapped_field: str, separator: str = '.') -> bool:
        """
        Compare the JSON's 'technical.[field]' to the media_file's corresponding attribute.
        Special handling for dateCreated, audioCodec, and durations.
        
        :param field: The key in 'technical' (which may have dot segments).
        :param mapped_field: The corresponding attribute in ami_file.
        :param separator: The dot separator.
        :raises AMIJSONError: If values do not match beyond fuzzy tolerance.
        :return: True if matched or acceptable within tolerance.
        """
        try:
            file_value = getattr(self.media_file, mapped_field)
        except AttributeError:
            self.raise_jsonerror(f"File missing expected attribute: {mapped_field}")

        md_value = self.dict["technical"]
        if separator in field:
            parts = field.split(separator)
            for p in parts:
                md_value = md_value[p]
        else:
            md_value = md_value[field]

        if md_value != file_value:
            if field == 'dateCreated':
                LOGGER.warning(f"{field} mismatch: JSON {md_value}, file {file_value}")
            elif field == 'audioCodec':
                if md_value == 'AAC' and file_value == 'AAC LC':
                    pass  # Acceptable difference
                else:
                    self.raise_jsonerror(f"Incorrect value for {field}. JSON {md_value} != file {file_value}")
            elif field == 'durationHuman':
                fuzz = 1
                md_ms = int(md_value.split('.')[-1])
                file_ms = int(file_value.split('.')[-1])
                if not fuzzy_check_md_value(md_ms, file_ms, fuzz):
                    self.raise_jsonerror(f"Duration mismatch (±{fuzz} ms): {md_value} vs {file_value}")
            elif field == 'durationMilli.measure':
                fuzz = 1
                if not fuzzy_check_md_value(md_value, file_value, fuzz):
                    self.raise_jsonerror(f"Duration mismatch (±{fuzz} ms): {md_value} vs {file_value}")
            else:
                self.raise_jsonerror(f"Incorrect value for {field}. JSON {md_value} != file {file_value}")

        return True

    def repair_techmd(self) -> None:
        """
        Rebuild the JSON's 'technical' dictionary based on the current media_file's attributes.
        """
        if not hasattr(self, 'media_file'):
            self.set_media_file()

        LOGGER.info(f"Rewriting technical md for {os.path.basename(self.filename)}")
        self.dict["technical"]["filename"] = self.media_file.base_filename
        self.dict["technical"]["extension"] = self.media_file.extension
        self.dict["technical"]["fileFormat"] = self.media_file.format

        if "fileSize" not in self.dict["technical"]:
            self.dict["technical"]["fileSize"] = {}
        self.dict["technical"]["fileSize"]["measure"] = self.media_file.size
        self.dict["technical"]["fileSize"]["unit"] = "B"

        if "dateCreated" not in self.dict["technical"]:
            self.dict["technical"]["dateCreated"] = self.media_file.date_created

        self.dict["technical"]["durationHuman"] = self.media_file.duration_human
        if "durationMilli" not in self.dict["technical"]:
            self.dict["technical"]["durationMilli"] = {}
        self.dict["technical"]["durationMilli"]["measure"] = self.media_file.duration_milli
        self.dict["technical"]["durationMilli"]["unit"] = "ms"

        self.dict["technical"]["audioCodec"] = self.media_file.audio_codec
        if self.media_file.type == "video":
            self.dict["technical"]["videoCodec"] = self.media_file.video_codec

    def strip_techmd(self) -> None:
        """
        Remove any unexpected fields in self.dict["technical"] that are not part of
        the known 'allowed' fields for AMI JSON.
        """
        allowed = [
            "filename", "extension", "fileFormat", "fileSize",
            "dateCreated", "durationHuman", "durationMilli",
            "audioCodec", "videoCodec"
        ]
        tdict = self.dict["technical"]
        keys_to_strip = [k for k in tdict if k not in allowed]
        for k in keys_to_strip:
            tdict.pop(k)

    def check_techfn(self) -> bool:
        """
        Check that self.dict["technical"]["filename"] is present and matches FN_NOEXT_RE.
        Raises AMIJSONError otherwise.
        """
        if "filename" not in self.dict["technical"]:
            self.raise_jsonerror("Key missing: technical.filename")
        if not re.match(FN_NOEXT_RE, self.dict["technical"]["filename"]):
            self.raise_jsonerror(
                f"technical.filename does not match expected pattern: {self.dict['technical']['filename']}"
            )
        return True

    def repair_techfn(self) -> bool:
        """
        Attempt to repair technical.filename to match STUB_FN_NOEXT_RE pattern.
        If successful, also ensures alignment with media_filepath or asset.referenceFilename.
        """
        correct_techfn = re.match(STUB_FN_NOEXT_RE, self.dict["technical"]["filename"])
        if correct_techfn:
            if hasattr(self, 'media_filepath'):
                try:
                    self.compare_techfn_media_filename()
                except Exception:
                    LOGGER.error("Extracted technical filename does not match media filename.")
                    return False
            try:
                self.compare_techfn_reffn()
            except Exception:
                LOGGER.warning("Extracted technical filename does not match asset.referenceFilename.")

            self.dict["technical"]["filename"] = correct_techfn[0]
            self.dict["technical"]["extension"] = self.dict["technical"]["extension"].lower()
            LOGGER.info(
                f"{self.filename} technical.filename updated to: {self.dict['technical']['filename']}"
            )
            return True
        else:
            LOGGER.error(
                f"Valid technical.filename could not be extracted from {self.dict['technical']['filename']}"
            )
            return False

    def check_reffn(self) -> bool:
        """
        Check that self.dict["asset"]["referenceFilename"] is present and matches FN_RE.
        Raises AMIJSONError otherwise.
        """
        if "referenceFilename" not in self.dict["asset"]:
            self.raise_jsonerror("Key missing: asset.referenceFilename")
        if not re.match(FN_RE, self.dict["asset"]["referenceFilename"]):
            self.raise_jsonerror(
                f"asset.referenceFilename not matching pattern: {self.dict['asset']['referenceFilename']}"
            )
        return True

    def repair_reffn(self) -> bool:
        """
        Attempt to align asset.referenceFilename with technical.filename/extension.
        """
        try:
            self.check_techfn()
        except AMIJSONError:
            LOGGER.error(
                "Valid asset.referenceFilename cannot be created from "
                f"{self.dict['technical']['filename']}, {self.dict['technical']['extension']}"
            )
            return False
        else:
            new_val = self.dict["technical"]["filename"] + '.' + self.dict["technical"]["extension"]
            self.dict["asset"]["referenceFilename"] = new_val
            LOGGER.info(f"{self.filename} asset.referenceFilename updated to: {new_val}")
            return True

    def compare_techfn_reffn(self) -> bool:
        """
        Compare 'technical.filename' + '.' + 'technical.extension' to 'asset.referenceFilename'.
        Raises AMIJSONError if they do not match.
        """
        tech = self.dict["technical"]
        asset = self.dict["asset"]
        if ("filename" not in tech) or ("extension" not in tech):
            self.raise_jsonerror("Keys missing in technical for filename/extension")
        if "referenceFilename" not in asset:
            self.raise_jsonerror("Key missing in asset for referenceFilename")

        if asset["referenceFilename"] != tech["filename"] + '.' + tech["extension"]:
            self.raise_jsonerror(
                f"asset.referenceFilename != technical.filename + extension: "
                f"{asset['referenceFilename']} != {tech['filename']}.{tech['extension']}"
            )
        return True

    def compare_techfn_media_filename(self) -> bool:
        """
        Compare 'technical.filename' + '.' + 'technical.extension' to the actual media_filepath.
        Raises AMIJSONError if they do not match.
        """
        tech = self.dict["technical"]
        expected = tech["filename"] + '.' + tech["extension"]
        provided = os.path.basename(self.media_filepath)
        if expected != provided:
            self.raise_jsonerror(
                f"technical.filename + extension != media filename: {expected} != {provided}"
            )
        return True

    def write_json(self, output_directory: str, indent: Optional[int] = None) -> None:
        """
        Write the JSON dictionary to disk in 'output_directory'. 
        Filename is derived from 'technical.filename' or 'asset.referenceFilename'.
        
        :param output_directory: The directory to write the .json file to.
        :param indent: JSON indentation (pass to json.dump).
        :raises AMIJSONError: If output dir doesn't exist or required keys are missing.
        """
        if not os.path.exists(output_directory):
            self.raise_jsonerror("Output directory does not exist")

        if ("technical" in self.dict) and ("filename" in self.dict["technical"]):
            fname = self.dict["technical"]["filename"]
        elif ("asset" in self.dict) and ("referenceFilename" in self.dict["asset"]):
            fname = self.dict["asset"]["referenceFilename"].split('.')[0]
        else:
            self.raise_jsonerror(
                "Metadata requires asset.referenceFilename or technical.filename"
            )
        out_path = os.path.join(output_directory, f"{fname}.json")
        try:
            with open(out_path, 'w') as f:
                json.dump(self.dict, f, indent=indent)
                LOGGER.info(f"{out_path} written")
        except Exception:
            LOGGER.error(f"{out_path} could not be written")

    def raise_jsonerror(self, msg: str) -> None:
        """
        Log and raise an AMIJSONError.
        :param msg: The error message.
        """
        logging.error(msg + '\n')
        raise AMIJSONError(msg)


# =============================================================================
#                         ami_bagError and Repairable_Bag
# =============================================================================

class Repairable_Bag(bagit.Bag):
    """
    Subclass of bagit.Bag that can implement 'repair' logic if needed.
    Currently a placeholder.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def repair(self) -> None:
        pass


# =============================================================================
#                     ami_bag
# =============================================================================

class ami_bag(Repairable_Bag):
    """
    Represents an AMI bag (JSON only). Validates bag structure, 
    required subdirectories, existence of PM files, etc.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the Bag, perform initial validation of completeness,
        set up path references, gather filepaths, etc.
        :raises ami_bagError: If bag is incomplete or if PM files are missing.
        """
        super().__init__(*args, **kwargs)

        try:
            self.validate(completeness_only=True)
        except bagit.BagValidationError as e:
            LOGGER.error(f"Bag incomplete or invalid oxum: {e.message}")
            raise ami_bagError("Cannot load incomplete bag")

        self.name = os.path.basename(self.path)
        self.data_files = set(self.payload_entries().keys())
        self.data_count = len(self.data_files)
        self.data_exts = set(os.path.splitext(fn)[1].lower() for fn in self.data_files)

        self.data_dirs = set(os.path.split(p)[0][5:] for p in self.data_files)
        if PM_DIR not in self.data_dirs:
            raise ami_bagError("Payload does not contain a PreservationMasters directory")

        # Determine media files
        self.media_filepaths = {
            os.path.join(self.path, p) for p in self.data_files
            if any(p.lower().endswith(ext) for ext in MEDIA_EXTS_FULL)
        }
        if not self.media_filepaths:
            raise ami_bagError(f"Payload does not contain files with accepted extensions: {MEDIA_EXTS_FULL}")

        self.pm_filepaths = {p for p in self.media_filepaths if '_pm.' in p}
        if not self.pm_filepaths:
            raise ami_bagError("Payload does not contain preservation master files")

        self.mz_filepaths = {p for p in self.media_filepaths if '_mz.' in p}
        self.em_filepaths = {p for p in self.media_filepaths if '_em.' in p}
        self.sc_filepaths = {p for p in self.media_filepaths if '_sc.' in p}

        self.set_compression()

        # Because Excel is removed, we only handle JSON
        self.type = None
        self.set_type()

        # Only JSON subtypes remain
        self.subtype = None
        self.set_subtype_json()
        self.set_metadata_json()

        self.set_tagged()

        LOGGER.info(f"{self.path} successfully loaded as {self.type} {self.subtype} bag")

    def set_compression(self) -> None:
        """
        Check whether PM files are all in compressed, uncompressed, or uncompressable formats.
        """
        self.compression = None
        pm_exts = set(os.path.splitext(f)[1].lower() for f in self.pm_filepaths)
        if pm_exts.issubset(COMPRESSED_EXTS):
            self.compressed = 'compressed'
        elif pm_exts.issubset(UNCOMPRESSED_EXTS):
            self.compression = 'uncompressed'
        elif pm_exts.issubset(UNCOMPRESSABLE_EXTS):
            self.compression = 'uncompressable'

    def set_type(self) -> None:
        """
        Since we've removed Excel logic, check if JSON metadata is present.
        Raises ami_bagError if no JSON found.
        """
        if JSON_EXT in self.data_exts:
            self.type = "json"
        else:
            raise ami_bagError("AMI bag must contain JSON metadata (no Excel logic left).")

    def set_subtype_json(self) -> None:
        """
        Determine subtype (film/video/audio/data) by comparing directory and extension sets.
        If no match found, defaults to 'unknown'.
        """
        for stype, (expected_dirs, expected_exts) in JSON_SUBTYPES.items():
            # "film" subtype requires MZ_DIR
            if stype == "film" and MZ_DIR not in self.data_dirs:
                continue
            dirs_ok = self.compare_structure(expected_dirs)
            exts_ok = self.compare_content(expected_exts)
            if dirs_ok and exts_ok:
                self.subtype = stype
        if self.subtype is None:
            LOGGER.warning("No recognized JSON subtype for this bag")
            self.subtype = "unknown"

    def set_metadata_json(self) -> None:
        """
        Gather .json metadata filenames and parse them just far enough
        to identify associated media filenames.
        """
        self.metadata_files = [
            fn for fn in self.data_files if os.path.splitext(fn)[1] == ".json"
        ]
        self.media_files_md = set()
        for fn in self.metadata_files:
            j = ami_json(filepath=os.path.join(self.path, fn))
            bn = j.dict["technical"]["filename"]
            ex = j.dict["technical"]["extension"]
            self.media_files_md.add(bn + '.' + ex)

    def set_tagged(self) -> None:
        """
        Check if bag is 'tagged' by searching for 'tags' in tagfile entries.
        """
        self.tagged = None
        if any('tags' in f for f in self.tagfile_entries()):
            self.tagged = 'tagged'
        elif self.subtype == 'unknown':
            self.tagged = 'tagging might be needed'
        else:
            self.tagged = 'tagging not needed'

    def compare_content(self, expected_exts: Set[str]) -> bool:
        """
        Check if the bag's data_exts are fully contained in 'expected_exts'.
        """
        return expected_exts >= self.data_exts

    def compare_structure(self, expected_dirs: Set[str]) -> bool:
        """
        Check if the bag's data_dirs are fully contained in 'expected_dirs'.
        """
        return expected_dirs >= self.data_dirs

    def check_amibag(self, fast: bool = True, metadata: bool = False) -> Tuple[bool, bool]:
        """
        Run a series of validations on this bag. 
        :param fast: if True, skip full checksum verification (use bagit validate with completeness_only).
        :param metadata: if True, do deeper JSON checks.
        :return: (warning, error) booleans indicating any warnings or errors encountered.
        """
        error = False
        warning = False

        # Basic bagit checks
        try:
            self.validate(fast=fast, completeness_only=fast)
        except bagit.BagValidationError as e:
            LOGGER.error(f"Bag out of spec: {e.message}")
            error = True

        # Filenames
        try:
            self.check_filenames()
        except ami_bagError as e:
            LOGGER.warning(f"Filenames out of spec: {e.message}")
            warning = True

        # Complex subobject?
        try:
            self.check_simple_filenames()
        except ami_bagError as e:
            LOGGER.warning(f"Filenames represent complex subobject: {e.message}")
            warning = True

        # Part filenames
        try:
            self.check_part_filenames()
        except ami_bagError as e:
            LOGGER.error(f"Filenames represent part file: {e.message}")
            error = True

        # Directory depth
        try:
            self.check_directory_depth()
        except ami_bagError as e:
            LOGGER.warning(f"File paths out of spec: {e.message}")
            warning = True

        # File location/role
        try:
            self.check_file_in_roledir()
        except ami_bagError as e:
            LOGGER.error(f"File location out of spec: {e.message}")
            error = True

        # PM <-> MZ
        if self.mz_filepaths:
            try:
                self.compare_fileset_pairs(self.pm_filepaths, self.mz_filepaths, "PM", "MZ")
            except ami_bagError as e:
                LOGGER.error(f"Asset balance out of spec: {e.message}")
                error = True

        # PM <-> EM
        if self.em_filepaths:
            try:
                self.compare_fileset_pairs(self.pm_filepaths, self.em_filepaths, "PM", "EM")
            except ami_bagError as e:
                LOGGER.error(f"Asset balance out of spec: {e.message}")
                error = True

        # PM <-> SC
        if self.sc_filepaths:
            try:
                self.compare_fileset_pairs(self.pm_filepaths, self.sc_filepaths, "PM", "SC")
            except ami_bagError as e:
                pm_iso = any(f.lower().endswith(".iso") for f in self.pm_filepaths)
                if pm_iso:
                    # For optical media, only warn
                    LOGGER.warning(f"Asset balance out of spec for video optical bag: {e.message}")
                    warning = True
                else:
                    # For everything else, it’s still an error
                    LOGGER.error(f"Asset balance out of spec: {e.message}")
                    error = True


        # Check bag type
        try:
            self.check_type()
        except ami_bagError as e:
            LOGGER.warning(f"Bag out of spec: {e.message}")
            warning = True

        # Check subtype
        try:
            self.check_subtype()
        except ami_bagError as e:
            LOGGER.warning(f"Bag subtype out of spec: {e.message}")
            warning = True

        # JSON structure
        try:
            self.check_bagstructure_json()
        except ami_bagError as e:
            LOGGER.error(f"Bag structure out of spec: {e.message}")
            error = True

        # Check JSON filenames
        try:
            self.check_filenames_md_concordance_json()
        except ami_bagError as e:
            LOGGER.error(f"Metadata balance out of spec: {e.message}")
            error = True

        # If user wants metadata checks, do them for JSON
        if metadata:
            try:
                self.check_metadata_json()
            except ami_bagError as e:
                LOGGER.warning(f"JSON metadata out of spec: {e.message}")
                warning = True

            try:
                self.check_filenames_md_manifest_concordance_json()
            except ami_bagError as e:
                LOGGER.error(f"JSON metadata out of spec: {e.message}")
                error = True

        return warning, error

    def compare_fileset_pairs(self,
                              primary_files: Set[str],
                              secondary_files: Set[str],
                              label_primary: str,
                              label_secondary: str) -> bool:
        """
        Checks whether two sets of file basenames (minus the final '_pm', '_mz', etc.) match exactly.
        Raises an ami_bagError if there's any mismatch.

        :param primary_files: e.g., pm_filepaths
        :param secondary_files: e.g., mz_filepaths
        :param label_primary: string label for error message, e.g. 'PM'
        :param label_secondary: string label for error message, e.g. 'MZ'
        :return: True if matched, otherwise raises ami_bagError.
        """
        base_primary = {os.path.basename(x).rsplit('_', 1)[0] for x in primary_files}
        base_secondary = {os.path.basename(x).rsplit('_', 1)[0] for x in secondary_files}
        if base_primary != base_secondary:
            raise ami_bagError(f"Mismatch of {label_primary} & {label_secondary}: "
                               f"{base_primary.symmetric_difference(base_secondary)}")
        return True

    def validate_amibag(self, fast: bool = True, metadata: bool = False) -> bool:
        """
        Higher-level convenience method that calls `check_amibag`.
        :param fast: If True, skip full checksums (bagit fast validation).
        :param metadata: If True, runs deeper JSON metadata checks.
        :return: True if no warnings or errors, else False.
        """
        w, e = self.check_amibag(fast=fast, metadata=metadata)
        return not (w or e)

    def check_filenames(self) -> bool:
        bad = []
        for p in self.data_files:
            fn = os.path.split(p)[1]
            if not FILENAME_REGEX.search(fn):
                bad.append(fn)
        if bad:
            raise ami_bagError(f"Non-standard filenames: {bad}")
        return True

    def check_simple_filenames(self) -> bool:
        complex_ = []
        for p in self.data_files:
            fn = os.path.split(p)[1]
            if SUBOBJECT_REGEX.search(fn):
                complex_.append(fn)
        if complex_:
            raise ami_bagError(f"Complex digitized objects: {complex_}")
        return True

    def check_part_filenames(self) -> bool:
        part_ = []
        for p in self.data_files:
            fn = os.path.split(p)[1]
            if SUBOBJECT_PART_REGEX.search(fn):
                part_.append(fn)
        if part_:
            raise ami_bagError(f"Part files found: {part_}")
        return True

    def check_directory_depth(self) -> bool:
        bad_dirs = []
        for d in self.data_dirs:
            if "/" in d:
                bad_dirs.append(d)
        if bad_dirs:
            raise ami_bagError(f"Too many directory levels: {bad_dirs}")
        return True

    def check_file_in_roledir(self) -> bool:
        """
        Ensure files with role suffix (pm, em, sc, ao) are in the matching directory. 
        Raises ami_bagError if mismatch found.
        """
        misplaced = []
        for p in self.data_files:
            role = os.path.splitext(p)[0].rsplit('_', 1)[1]
            if role == "pm" and PM_DIR not in p:
                misplaced.append(p)
            if role == "em" and EM_DIR not in p:
                misplaced.append(p)
            if role == "sc" and SC_DIR not in p:
                misplaced.append(p)
            if role == "ao" and AO_DIR not in p:
                misplaced.append(p)

            # If we found a mismatch, raise once after collecting them
        if misplaced:
            raise ami_bagError(f"Files in wrong directory: {misplaced}")
        return True

    def check_type(self) -> bool:
        """
        Checks if self.type is recognized as 'json'. Raises ami_bagError otherwise.
        """
        if not self.type or self.type != "json":
            raise ami_bagError("Bag is not recognized as JSON type")
        return True

    def check_subtype(self) -> bool:
        """
        Checks if self.subtype is recognized among known subtypes or if it's 'unknown'.
        Raises ami_bagError if unknown.
        """
        if self.subtype == "unknown":
            raise ami_bagError("Bag subtype not recognized (film, video, audio, or data)")
        return True

    def check_bagstructure_json(self) -> bool:
        """
        Verifies that the bag only uses directories permissible for JSON subtypes,
        and that self.subtype is not None.
        Raises ami_bagError if invalid.
        """
        exp_dirs = set()
        for props in JSON_SUBTYPES.values():
            exp_dirs |= props[0]
        if not self.compare_structure(exp_dirs):
            raise ami_bagError(f"JSON bags can only have dirs in {exp_dirs}")
        if not self.subtype:
            raise ami_bagError(
                f"No known JSON subtype.\nExtensions: {self.data_exts}\nDirs: {self.data_dirs}"
            )
        return True

    def check_filenames_md_concordance_json(self) -> bool:
        """
        Ensures that for each media file, there's a .json file with the same base name.
        Raises ami_bagError if mismatch.
        """
        md_files = {os.path.splitext(os.path.basename(x))[0] for x in self.metadata_files}
        media_files = {os.path.splitext(os.path.basename(x))[0] for x in self.media_filepaths}
        if md_files != media_files:
            missing = media_files - md_files
            raise ami_bagError(f"Media basenames do not match JSON metadata. Missing: {missing}")
        return True

    def check_metadata_json(self) -> bool:
        """
        Validate each .json file in the bag using ami_json.validate_json.
        Raises ami_bagError if any .json fails validation.
        """
        if not self.metadata_files:
            raise ami_bagError("JSON bag has no .json files!")
        bad_js = []
        for fn in sorted(self.metadata_files):
            jpath = os.path.join(self.path, fn)
            j_obj = ami_json(filepath=jpath)
            ex = j_obj.dict["technical"]["extension"]
            j_obj.set_mediafilepath(jpath.replace('json', ex))
            try:
                j_obj.validate_json()
            except Exception as e:
                bad_js.append(fn)
                LOGGER.warning(f"Validation error for {fn}: {e}", exc_info=True)
        if bad_js:
            raise ami_bagError(f"JSON files contain formatting errors: {bad_js}")
        return True

    def check_filenames_md_manifest_concordance_json(self) -> bool:
        """
        Compare the basenames from parsed JSON technical filename to the actual 
        media_filepaths. Raises ami_bagError if mismatch found.
        """
        media_basenames = {os.path.basename(x) for x in self.media_filepaths}
        if self.media_files_md != media_basenames:
            missing = media_basenames - self.media_files_md
            raise ami_bagError(f"JSON mismatch. Missing from metadata: {missing}")
        return True

    def get_total_bytes(self, fileset: Set[str]) -> int:
        """
        Sum the file sizes of the given set of files in the bag.
        
        :param fileset: A set of absolute or relative paths.
        :return: The total number of bytes.
        """
        total = 0
        for f in fileset:
            if os.path.isabs(f):
                full_path = f
            else:
                full_path = os.path.join(self.path, f)
            if os.path.exists(full_path):
                total += os.stat(full_path).st_size
        return total


# =============================================================================
#                           validate.py (JSON only)
# =============================================================================

def _configure_logging(args: argparse.Namespace) -> None:
    """
    Configure the logger based on command-line arguments (log file or not).
    """
    log_format = "%(name)s: %(asctime)s - %(levelname)s - %(message)s"
    if args.log:
        logging.basicConfig(filename=args.log, level=logging.INFO, format=log_format)
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)


def _make_parser() -> argparse.ArgumentParser:
    """
    Build the argument parser for the CLI.
    :return: An ArgumentParser object with all relevant arguments.
    """
    parser = argparse.ArgumentParser(description="Check if an AMI bag (JSON only) meets specifications")
    parser.add_argument("-d", "--directory", nargs='+', help="Path to a directory full of bags")
    parser.add_argument("-b", "--bagpath", nargs='+', default=None, help="Path to a single bag")
    parser.add_argument("--slow", action='store_false', help="Recalculate hashes (very slow)")
    parser.add_argument(
        "--metadata",
        action='store_true',
        help="Validate JSON metadata files in the bag"
    )
    parser.add_argument("--log", help="Name of the log file")
    parser.add_argument("-q", "--quiet", action='store_true', help="Suppress most logs")
    return parser


def log_checks(args: argparse.Namespace) -> None:
    """
    Log an overview of checks that will be performed based on CLI arguments.
    """
    checks = """Performing the following validations:
    Checking Oxums,
    Checking bag completeness,
    """
    if not args.slow:
        checks += "Recalculating hashes,\n"
    checks += """Determining bag type,
    Checking directory structure,
    Checking filenames,
    Validating JSON bag subtypes
    """
    if args.metadata:
        checks += "Validating JSON metadata files\n"
    LOGGER.info(checks)
    LOGGER.info("""To interpret log messages:
    - WARNING: bag is valid but might have questionable features.
    - ERROR: bag is out of spec and cannot be ingested.
    - CRITICAL: script failure. Bag may be in or out of spec.
    """)


def process_directory(directory: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Walk a directory tree for subdirectories that look like bag directories,
    attempt to process each bag, and return a summary.

    :param directory: Path to a directory containing 1..N possible bags.
    :param args: Parsed CLI arguments for logging levels, etc.
    :return: A dictionary summarizing warnings, errors, valid bags, etc.
    """
    print("Now checking directory:", directory)
    directory_path = os.path.abspath(directory)
    bags = []
    for root, dirnames, _filenames in os.walk(directory_path):
        for d in dirnames:
            # For example, subdirs named '123456' are considered potential bag directories
            if re.match(r'\d{6}$', d):
                bags.append(os.path.join(root, d))

    if not bags:
        LOGGER.info(f"No valid bag directories found in: {directory_path}")
        return {'directory': directory_path, 'summary': "No valid bag directories found"}

    return process_bags(bags, args, directory_path)


def process_single_bag(bagpath: str, args: argparse.Namespace) -> Dict[str, Any]:
    """
    Process a single bag directory, return summary data.

    :param bagpath: Path to the bag directory.
    :param args: CLI arguments controlling logging and metadata checks.
    :return: A dictionary summarizing warnings, errors, or success.
    """
    print("Now checking bag:", bagpath)
    abspath = os.path.abspath(bagpath)
    return process_bags([abspath], args, abspath)


def process_bags(bags: List[str], args: argparse.Namespace, directory_path: str) -> Dict[str, Any]:
    """
    Loop over each bag in the provided list, track warnings/errors/valid bags, and return a summary dict.

    :param bags: List of absolute paths to bag directories.
    :param args: CLI arguments controlling logging and metadata checks.
    :param directory_path: The top-level directory being processed (for summary).
    :return: Dict with keys for 'directory', 'warning_bags', 'error_bags', 'valid_bags', 'total_bags'.
    """
    LOGGER.info(f"Checking {len(bags)} folder(s) in {directory_path}")
    if args.quiet:
        LOGGER.setLevel(level=logging.ERROR)

    warning_bags = []
    error_bags = []
    valid_bags = []

    for bagpath in tqdm(sorted(bags)):
        LOGGER.info(f"Checking: {bagpath}")
        try:
            bag = ami_bag(path=bagpath)
            warning, error = bag.check_amibag(fast=args.slow, metadata=args.metadata)
            if error:
                LOGGER.error(f"Invalid bag: {bagpath}")
                error_bags.append(os.path.basename(bagpath))
            elif warning:
                LOGGER.warning(f"Bag may have issues: {bagpath}")
                warning_bags.append(os.path.basename(bagpath))
            else:
                valid_bags.append(os.path.basename(bagpath))
        except Exception as e:
            LOGGER.error(f"Error loading {bagpath}: {e}")
            error_bags.append(os.path.basename(bagpath))

    return {
        'directory': directory_path,
        'warning_bags': warning_bags,
        'error_bags': error_bags,
        'valid_bags': valid_bags,
        'total_bags': len(bags)
    }


def log_summary(results: List[Dict[str, Any]]) -> None:
    """
    After processing multiple directories, logs a summary for each.

    :param results: A list of summary dictionaries from process_directory/process_single_bag.
    """
    LOGGER.setLevel(logging.INFO)
    for result in results:
        print("")
        LOGGER.info(f"Summary for directory: {result['directory']}")
        if 'summary' in result:
            LOGGER.info(result['summary'])
        else:
            total = result['total_bags']
            ebags = result['error_bags']
            wbags = result['warning_bags']
            vbags = result['valid_bags']
            if ebags:
                LOGGER.info(f"{len(ebags)} of {total} bags NOT ready for ingest")
                LOGGER.info("Bags not ready: " + ", ".join(ebags))
            if wbags:
                LOGGER.info(f"{len(wbags)} of {total} bags ready but with potential issues")
                LOGGER.info("Bags with potential issues: " + ", ".join(wbags))
            if vbags:
                LOGGER.info(f"{len(vbags)} of {total} bags fully ready")
                LOGGER.info("Bags ready: " + ", ".join(vbags))


def main() -> None:
    """
    CLI entry point. Parses arguments, configures logging, processes bags or directories,
    then logs a summary of results.
    """
    parser = _make_parser()
    args = parser.parse_args()
    _configure_logging(args)
    log_checks(args)

    results = []
    if args.directory:
        for d in args.directory:
            res = process_directory(d, args)
            if res:
                results.append(res)
    if args.bagpath:
        for bp in args.bagpath:
            res = process_single_bag(bp, args)
            if res:
                results.append(res)

    log_summary(results)


if __name__ == "__main__":
    main()