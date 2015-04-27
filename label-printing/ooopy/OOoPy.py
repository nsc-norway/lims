#!/usr/bin/env python
# -*- coding: iso-8859-1 -*-
# Copyright (C) 2005-14 Dr. Ralf Schlatterbeck Open Source Consulting.
# Reichergasse 131, A-3411 Weidling.
# Web: http://www.runtux.com Email: office@runtux.com
# All rights reserved
# ****************************************************************************
#
# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Library General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU Library General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
# ****************************************************************************

from __future__              import absolute_import

from zipfile                 import ZipFile, ZIP_DEFLATED, ZipInfo
try :
    from StringIO            import StringIO
except ImportError :
    from io                  import StringIO
from datetime                import datetime
try :
    from xml.etree.ElementTree   import ElementTree, fromstring, _namespace_map
except ImportError :
    from elementtree.ElementTree import ElementTree, fromstring, _namespace_map
from tempfile                import mkstemp
from ooopy.Version           import VERSION
import os

class _autosuper (type) :
    def __init__ (cls, name, bases, dict) :
        super   (_autosuper, cls).__init__ (name, bases, dict)
        setattr (cls, "_%s__super" % name, super (cls))
    # end def __init__
# end class _autosuper

class autosuper (object) :
    __metaclass__ = _autosuper
    def __init__ (self, *args, **kw) :
        self.__super.__init__ ()
    # end def __init__
# end class autosuper

files = \
    [ 'content.xml'
    , 'styles.xml'
    , 'meta.xml'
    , 'settings.xml'
    , 'META-INF/manifest.xml'
    ]

mimetypes = \
    [ 'application/vnd.sun.xml.writer'
    , 'application/vnd.oasis.opendocument.text'
    ]
namespace_by_name = \
  { mimetypes [0] :
      { 'chart'    : "http://openoffice.org/2000/chart"
      , 'config'   : "http://openoffice.org/2001/config"
      , 'dc'       : "http://purl.org/dc/elements/1.1/"
      , 'dr3d'     : "http://openoffice.org/2000/dr3d"
      , 'draw'     : "http://openoffice.org/2000/drawing"
      , 'fo'       : "http://www.w3.org/1999/XSL/Format"
      , 'form'     : "http://openoffice.org/2000/form"
      , 'math'     : "http://www.w3.org/1998/Math/MathML"
      , 'meta'     : "http://openoffice.org/2000/meta"
      , 'number'   : "http://openoffice.org/2000/datastyle"
      , 'office'   : "http://openoffice.org/2000/office"
      , 'script'   : "http://openoffice.org/2000/script"
      , 'style'    : "http://openoffice.org/2000/style"
      , 'svg'      : "http://www.w3.org/2000/svg"
      , 'table'    : "http://openoffice.org/2000/table"
      , 'text'     : "http://openoffice.org/2000/text"
      , 'xlink'    : "http://www.w3.org/1999/xlink"
      , 'manifest' : "http://openoffice.org/2001/manifest"
      }
  , mimetypes [1] :
      { 'chart'    : "urn:oasis:names:tc:opendocument:xmlns:chart:1.0"
      , 'config'   : "urn:oasis:names:tc:opendocument:xmlns:config:1.0"
      , 'dc'       : "http://purl.org/dc/elements/1.1/"
      , 'dr3d'     : "urn:oasis:names:tc:opendocument:xmlns:dr3d:1.0"
      , 'draw'     : "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
      , 'fo'       : "urn:oasis:names:tc:opendocument:xmlns:"
                     "xsl-fo-compatible:1.0"
      , 'form'     : "urn:oasis:names:tc:opendocument:xmlns:form:1.0"
      , 'math'     : "http://www.w3.org/1998/Math/MathML"
      , 'meta'     : "urn:oasis:names:tc:opendocument:xmlns:meta:1.0"
      , 'number'   : "urn:oasis:names:tc:opendocument:xmlns:datastyle:1.0"
      , 'office'   : "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      , 'officeooo': "http://openoffice.org/2009/office"
      , 'script'   : "urn:oasis:names:tc:opendocument:xmlns:script:1.0"
      , 'style'    : "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
      , 'svg'      : "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0"
      , 'table'    : "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
      , 'text'     : "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
      , 'xlink'    : "http://www.w3.org/1999/xlink"
      , 'manifest' : "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"
      , 'tableooo' : "http://openoffice.org/2009/table"
      , 'transformation' : "http://www.w3.org/2003/g/data-view#"
      # OOo 1.X tags and some others:
      , 'ooo'      : "http://openoffice.org/2004/office"
      , 'ooow'     : "http://openoffice.org/2004/writer"
      , 'oooc'     : "http://openoffice.org/2004/calc"
      , 'o_dom'    : "http://www.w3.org/2001/xml-events"
      , 'o_xforms' : "http://www.w3.org/2002/xforms"
      , 'xs'       : "http://www.w3.org/2001/XMLSchema"
      , 'xsi'      : "http://www.w3.org/2001/XMLSchema-instance"
      # predefined xml namespace, see
      # http://www.w3.org/TR/2006/REC-xml-names11-20060816/
      # "It MAY, but need not, be declared, and MUST NOT be undeclared
      # or bound to any other namespace name."
      , 'xml'      : "http://www.w3.org/XML/1998/namespace"
      }
  }

for mimetype in namespace_by_name.itervalues () :
    for k, v in mimetype.iteritems () :
        if v in _namespace_map :
            assert (_namespace_map [v] == k)
        _namespace_map [v] = k

class OOoElementTree (autosuper) :
    """
        An ElementTree for OOo document XML members. Behaves like the
        orginal ElementTree (in fact it delegates almost everything to a
        real instance of ElementTree) except for the write method, that
        writes itself back to the OOo XML file in the OOo zip archive it
        came from.
    """
    def __init__ (self, ooopy, zname, root) :
        self.ooopy = ooopy
        self.zname = zname
        self.tree  = ElementTree (root)
    # end def __init__

    def write (self) :
        self.ooopy.write (self.zname, self.tree)
    # end def write

    def __getattr__ (self, name) :
        """
            Delegate everything to our ElementTree attribute.
        """
        if not name.startswith ('__') :
            result = getattr (self.tree, name)
            setattr (self, name, result)
            return result
        raise AttributeError (name)
    # end def __getattr__

# end class OOoElementTree

class OOoPy (autosuper) :
    """
        Wrapper for OpenOffice.org zip files (all OOo documents are
        really zip files internally).

        from ooopy.OOoPy import OOoPy
        >>> o = OOoPy (infile = 'testfiles/test.sxw', outfile = 'out.sxw')
        >>> o.mimetype
        'application/vnd.sun.xml.writer'
        >>> for f in files :
        ...     e = o.read (f)
        ...     e.write ()
        ...
        >>> o.close ()
        >>> o = OOoPy (infile = 'testfiles/test.odt', outfile = 'out2.odt')
        >>> o.mimetype
        'application/vnd.oasis.opendocument.text'
        >>> for f in files :
        ...     e = o.read (f)
        ...     e.write ()
        ...
        >>> o.append_file ('Pictures/empty', '')
        >>> o.close ()
        >>> o = OOoPy (infile = 'out2.odt')
        >>> for f in o.izip.infolist () :
        ...     print f.filename, f.create_system, f.compress_type
        mimetype 0 8
        content.xml 0 8
        styles.xml 0 8
        meta.xml 0 8
        settings.xml 0 8
        META-INF/manifest.xml 0 8
        Pictures/empty 0 8
        Configurations2/statusbar/ 0 0
        Configurations2/accelerator/current.xml 0 8
        Configurations2/floater/ 0 0
        Configurations2/popupmenu/ 0 0
        Configurations2/progressbar/ 0 0
        Configurations2/menubar/ 0 0
        Configurations2/toolbar/ 0 0
        Configurations2/images/Bitmaps/ 0 0
        Thumbnails/thumbnail.png 0 8
    """
    def __init__ \
        ( self
        , infile     = None
        , outfile    = None
        , write_mode = 'w'
        , mimetype   = None
        ) :
        """
            Open an OOo document, if no outfile is given, we open the
            file read-only. Otherwise the outfile has to be different
            from the infile -- the python ZipFile can't deal with
            read-write access. In case an outfile is given, we open it
            in "w" mode as a zip file, unless write_mode is specified
            (the only allowed case would be "a" for appending to an
            existing file, see pythons ZipFile documentation for
            details). If no infile is given, the user is responsible for
            providing all necessary files in the resulting output file.

            It seems that OOo needs to have the mimetype as the first
            archive member (at least with mimetype as the first member
            it works, the order may not be arbitrary) to recognize a zip
            archive as an OOo file. When copying from a given infile, we
            use the same order of elements in the resulting output. When
            creating new elements we make sure the mimetype is the first
            in the resulting archive.

            Note that both, infile and outfile can either be filenames
            or file-like objects (e.g. StringIO).

            The mimetype is automatically determined if an infile is
            given. If only writing is desired, the mimetype should be
            set.
        """
        assert (infile != outfile)
        self.izip = self.ozip = None
        if infile :
            self.izip    = ZipFile (infile,  'r',        ZIP_DEFLATED)
        if outfile :
            self.ozip    = ZipFile (outfile, write_mode, ZIP_DEFLATED)
            self.written = {}
        if mimetype :
            self.mimetype = mimetype
        elif self.izip :
            self.mimetype = self.izip.read ('mimetype')
    # end def __init__

    def read (self, zname) :
        """
            return an OOoElementTree object for the given OOo document
            archive member name. Currently an OOo document contains the
            following XML files::

             * content.xml: the text of the OOo document
             * styles.xml: style definitions
             * meta.xml: meta-information (author, last changed, ...)
             * settings.xml: settings in OOo
             * META-INF/manifest.xml: contents of the archive

            There is an additional file "mimetype" that always contains
            the string "application/vnd.sun.xml.writer" for OOo 1.X files
            and the string "application/vnd.oasis.opendocument.text" for
            OOo 2.X files.
        """
        assert (self.izip)
        return OOoElementTree (self, zname, fromstring (self.izip.read (zname)))
    # end def read

    def _write (self, zname, str) :
        now  = datetime.utcnow ().timetuple ()
        info = ZipInfo (zname, date_time = now)
        info.create_system = 0 # pretend to be fat
        info.compress_type = ZIP_DEFLATED
        self.ozip.writestr (info, str)
        self.written [zname] = 1
    # end def _write

    def write (self, zname, etree) :
        assert (self.ozip)
        # assure mimetype is the first member in new archive
        if 'mimetype' not in self.written :
            self._write ('mimetype', self.mimetype)
        str = StringIO ()
        etree.write (str)
        self._write (zname, str.getvalue ())
    # end def write

    def append_file (self, zname, str) :
        """ Official interface to _write: Append a file to the end of
            the archive.
        """
        if zname not in self.written :
            self._write (zname, str)
    # end def append_file

    def close (self) :
        """
            Close the zip files. According to documentation of zipfile in
            the standard python lib, this has to be done to be sure
            everything is written. We copy over the not-yet written files
            from izip before closing ozip.
        """
        if self.izip and self.ozip :
            for f in self.izip.infolist () :
                if f.filename not in self.written :
                    self.ozip.writestr (f, self.izip.read (f.filename))
        for i in self.izip, self.ozip :
            if i : i.close ()
        self.izip = self.ozip = None
    # end def close

    __del__ = close # auto-close on deletion of object
# end class OOoPy
