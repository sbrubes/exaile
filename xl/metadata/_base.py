# Copyright (C) 2008-2009 Adam Olsen
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
#
# The developers of the Exaile media player hereby grant permission
# for non-GPL compatible GStreamer and Exaile plugins to be used and
# distributed together with GStreamer and Exaile. This permission is
# above and beyond the permissions granted by the GPL license by which
# Exaile is covered. If you modify this code, you may extend this
# exception to your version of the code, but you are not obligated to
# do so. If you do not wish to do so, delete this exception statement
# from your version.

import copy
import logging
import os
import urllib2
import urlparse
import gio
from xl import common

logger = logging.getLogger(__name__)

INFO_TAGS = ['__bitrate', '__length']

class NotWritable(Exception):
    pass

class NotReadable(Exception):
    pass

class BaseFormat(object):
    MutagenType = None
    tag_mapping = {}
    others = True
    writable = False
    ignore_tags = ['coverart', 'cover', 'lyrics', 'Cover Art (front)']

    def __init__(self, loc):
        self.loc = loc
        self.open = False
        self.mutagen = None
        self.load()
        self._reverse_mapping = dict((
            (v,k) for k,v in self.tag_mapping.iteritems() ))

    def load(self):
        """
            Loads the tags from the file.
        """
        if self.MutagenType:
            try:
                self.mutagen = self.MutagenType(self.loc)
            except:
                logger.error("Couldn't read tags from possibly corrupt " \
                        "file %s" % self.loc)
                common.log_exception(logger)
                raise NotReadable

    def save(self):
        """
            Saves any changes to the tags.
        """
        if self.writable and self.mutagen:
            self.mutagen.save()

    def _get_raw(self):
        if self.MutagenType:
            return self.mutagen
        else:
            return {'title':self._get_fallback_title()}

    def _get_fallback_title(self):
        return gio.File(self.loc).get_basename()

    def _get_tag(self, raw, tag):
        try:
            return raw[tag]
        except KeyError:
            return None

    def _get_keys(self):
        keys = []
        for k in self._get_raw().keys():
            if k in self._reverse_mapping:
                keys.append(self._reverse_mapping[k])
            else:
                keys.append(k)
        if "title" not in keys:
            keys.append("title")
        return keys

    def read_all(self):
        tags = []
        for t in self._get_keys():
            if t in self.ignore_tags:
                continue
            if t.startswith("__"):
                logger.warning("Could not import tag %(tag)s from file "
                        "%(location)s because of possible conflict from "
                        "leading __, please adjust your tag names if you "
                        "want to import this tag." % \
                                {'tag': t, 'location': self.loc})
                continue
            tags.append(t)
        all = self.read_tags(tags)
        all.update(self.read_tags(INFO_TAGS))
        return all

    def read_tags(self, tags):
        """
            get the values for the specified tags.

            returns a dict of the found values. if no value was found for a
            requested tag it will not exist in the returned dict
        """
        raw = self._get_raw()
        td = {}
        for tag in tags:
            t = None
            if tag in INFO_TAGS:
                try:
                    t = self.get_info(tag)
                except KeyError:
                    pass
            if t == None and tag in self.tag_mapping:
                try:
                    t = self._get_tag(raw, self.tag_mapping[tag])
                    if type(t) in [str, unicode]:
                        t = [t]
                    else:
                        try:
                            t = [unicode(u) for u in list(t)]
                        except UnicodeDecodeError:
                            t = t
                except (KeyError, TypeError):
                    pass
            if t == None and self.others:
                try:
                    t = self._get_tag(raw, tag)
                    if type(t) in [str, unicode]:
                        t = [t]
                    else:
                        t = [unicode(u) for u in list(t)]
                except (KeyError, TypeError):
                    pass
            if t == None and tag == "title":
                t = self._get_fallback_title()

            if t not in [None, []]:
                td[tag] = t
        return td

    def _set_tag(self, raw, tag, value):
        raw[tag] = value

    def write_tags(self, tagdict):
        tagdict = copy.deepcopy(tagdict)
        if not self.MutagenType:
            raise NotWritable
        else:
            raw = self._get_raw()
            # add tags if it doesn't have them
            try:
                raw.add_tags()
            except:
#            except (ValueError, NotImplementedError):
                # FIXME: this is BAD to not tie specifically to an exception,
                # but mutagen doesn't provide a base error class to catch
                pass

            # info tags are not actually writable
            for tag in INFO_TAGS:
                try:
                    del tagdict[tag]
                except:
                    pass

            # tags starting with __ are internal and should not be written
            for tag in tagdict.keys():
                if tag.startswith("__"):
                    try:
                        del tagdict[tag]
                    except:
                        pass

            for tag in tagdict:
                if tag in self.tag_mapping:
                    self._set_tag(raw, self.tag_mapping[tag], tagdict[tag])
                elif self.others:
                    self._set_tag(raw, tag, tagdict[tag])
            self.save()

    def get_info(self, info):
        if info == "__length":
            return self.get_length()
        elif info == "__bitrate":
            return self.get_bitrate()
        else:
            raise KeyError

    def get_length(self):
        try:
            return self.mutagen.info.length
        except:
            try:
                return self.mutagen['__length']
            except:
                return None

    def get_bitrate(self):
        try:
            return self.mutagen.info.bitrate
        except:
            try:
                return self.mutagen['__bitrate']
            except:
                return None

# vim: et sts=4 sw=4

