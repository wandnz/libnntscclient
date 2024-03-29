#!/usr/bin/env python3
#
# This file is part of libnntscclient.
#
# Copyright (C) 2013-2017 The University of Waikato, Hamilton, New Zealand.
#
# Authors: Shane Alcock
#          Brendon Jones
#
# All rights reserved.
#
# This code has been developed by the WAND Network Research Group at the
# University of Waikato. For further information please see
# http://www.wand.net.nz/
#
# libnntscclient is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# libnntscclient is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with libnntscclient; if not, write to the Free Software Foundation, Inc.
# 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
# Please report any bugs, questions or comments to contact@wand.net.nz
#


import struct
import pickle
import zlib
from socket import *
from libnntscclient.protocol import *
import libnntscclient.logger as logger

class NNTSCClient:
    def __init__(self, sock):
        self.sock = sock
        self.buf = b""

    def disconnect(self):
        if self.sock != None:
            self.sock.close()
        self.sock = None

    def send_request(self, reqtype, col, start=0):
        if self.sock is None:
            logger.log("Cannot send NNTSC_REQUEST on a closed socket!")
            return -1

        if reqtype == NNTSC_REQ_COLLECTION:
            col = 0

        if reqtype == NNTSC_REQ_ACTIVE_STREAMS:
            logger.log("Requesting active streams is no longer supported by NNTSC")
            return -1

        request = struct.pack(nntsc_req_fmt, reqtype, col, start)

        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_REQUEST,
                struct.calcsize(nntsc_req_fmt))

        try:
            self.sock.sendall(header + request)
        except error:
            logger.log("Error sending NNTSC_REQUEST %d for collection %d: %s" % (reqtype, col, error))
            return -1

        return 0

    def subscribe_streams(self, name, columns, labels, start, end, aggs):
        if self.sock is None:
            logger.log("Cannot send NNTSC_SUBSCRIBE on a closed socket!")
            return -1

        # Our "labels" are actually a list of streams, which is how we used to
        # manage this sort of thing. Convert to the new label format for
        # backwards compatibility
        if type(labels) is list:
            labels = self.convert_streams_to_labels(labels)

        contents = pickle.dumps((name, start, end, columns, labels, aggs))
        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_SUBSCRIBE, len(contents))

        try:
            self.sock.sendall(header + contents)
        except error:
            logger.log("Error sending NNTSC_SUBSCRIBE for %s: %s" % (name, error))
            return -1

        return 0

    def unsubscribe_streams(self, colid, streams):
        if self.sock is None:
            logger.log("Cannot send NNTSC_UNSUBSCRIBE on a closed socket!")
            return -1

        contents = pickle.dumps((colid, streams))
        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_UNSUBSCRIBE, len(contents))

        try:
            self.sock.sendall(header + contents)
        except error:
            logger.log("Error sending NNTSC_UNSUBSCRIBE for %s: %s" % (colid, error))
            return -1

        return 0

    def request_matrix(self, col, labels, start, end, aggcolumns, aggfunc):
        if self.sock is None:
            logger.log("Cannot send NNTSC_MATRIX on a closed socket!")
            return -1

        # Our "labels" are actually a list of streams, which is how we used to
        # manage this sort of thing. Convert to the new label format for
        # backwards compatibility
        if type(labels) is list:
            labels = self.convert_streams_to_labels(labels)

        contents = pickle.dumps((col, start, end, labels, aggcolumns, aggfunc))
        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_MATRIX, len(contents))

        try:
            self.sock.sendall(header + contents)
        except error:
            logger.log("Error sending NNTSC_MATRIX for %s: %s" % (col, error))
            return -1

        return 0

    def request_aggregate(self, col, labels, start, end, aggcolumns, binsize,
            groupcolumns=None, aggfunc="avg"):

        if self.sock is None:
            logger.log("Cannot send NNTSC_AGGREGATE on a closed socket!")
            return -1

        if groupcolumns is None:
            groupcolumns = []

        # Our "labels" are actually a list of streams, which is how we used to
        # manage this sort of thing. Convert to the new label format for
        # backwards compatibility
        if type(labels) is list:
            labels = self.convert_streams_to_labels(labels)

        contents = pickle.dumps((col, start, end, labels, aggcolumns,
                groupcolumns, binsize, aggfunc))
        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_AGGREGATE, len(contents))

        try:
            self.sock.sendall(header + contents)
        except error:
            logger.log("Error sending NNTSC_AGGREGATE for %s: %s" % (col, error))
            return -1

        return 0

    def request_percentiles(self, col, labels, start, end, binsize,
            ntilecolumns, othercolumns=None, ntileaggfunc="avg",
            otheraggfunc="avg"):

        if self.sock is None:
            logger.log("Cannot send NNTSC_PERCENTILE on a closed socket!")
            return -1

        if othercolumns is None:
            othercolumns = []

        # Our "labels" are actually a list of streams, which is how we used to
        # manage this sort of thing. Convert to the new label format for
        # backwards compatibility
        if type(labels) is list:
            labels = self.convert_streams_to_labels(labels)

        contents = pickle.dumps((col, start, end, labels, binsize,
                ntilecolumns,
                othercolumns, ntileaggfunc, otheraggfunc))
        header = struct.pack(nntsc_hdr_fmt, 1, NNTSC_PERCENTILE, len(contents))

        try:
            self.sock.sendall(header + contents)
        except error:
            logger.log("Error sending NNTSC_PERCENTILE for %s: %s" % (col, error))
            return -1

        return 0


    def receive_message(self):
        if self.sock is None:
            logger.log("Cannot receive messages on a closed socket!")
            return -1

        try:
            received = self.sock.recv(256000)
        except error:
            logger.log("Error receiving data from client: %s" % error)
            return -1

        if len(received) == 0:
            return 0

        self.buf += received
        return len(received)

    def parse_message(self):
        if len(self.buf) < struct.calcsize(nntsc_hdr_fmt):
            return -1, {}

        header_end = struct.calcsize(nntsc_hdr_fmt)
        header = struct.unpack(nntsc_hdr_fmt, self.buf[0:header_end])

        total_len = header[2] + header_end

        if len(self.buf) < total_len:
            return -1, {}

        msgdict = {}

        if header[1] == NNTSC_VERSION_CHECK:
            version = pickle.loads(self.buf[header_end:total_len])
            if version != NNTSC_CLIENTAPI_VERSION:
                logger.log("Current NNTSC Client version %s does not match version required by server (%s)" % (NNTSC_CLIENTAPI_VERSION, version))
                logger.log("Closing client socket")
                # None tells the caller that they should disconnect
                return -1, None
            else:
                #logger.log("NNTSC Protocol version check passed")
                # Don't return these to the caller, just try and read
                # another message
                self.buf = self.buf[total_len:]
                return -1, {}

        if header[1] == NNTSC_COLLECTIONS:
            col_list = pickle.loads(self.buf[header_end:total_len])
            msgdict['collections'] = col_list

        if header[1] == NNTSC_SCHEMAS:
            name, ss, ds = pickle.loads(self.buf[header_end:total_len])
            msgdict['collection'] = name
            msgdict['streamschema'] = ss
            msgdict['dataschema'] = ds

        if header[1] == NNTSC_STREAMS:
            name, more, arrived = pickle.loads(self.buf[header_end:total_len])
            msgdict['collection'] = name
            msgdict['more'] = more
            msgdict['streams'] = arrived

        if header[1] == NNTSC_ACTIVE_STREAMS:
            logger.log("Current NNTSC Client version %s does not support ACTIVE_STREAMS messages" % (NNTSC_CLIENTAPI_VERSION))
            logger.log("Closing client socket")
            return -1, None

        if header[1] == NNTSC_HISTORY:
            compressed = self.buf[header_end:total_len]
            uncompressed = zlib.decompress(compressed)
            name, stream_id, data, more, binsize = pickle.loads(uncompressed)
            msgdict['collection'] = name
            msgdict['streamid'] = stream_id
            msgdict['data'] = data
            msgdict['more'] = more
            msgdict['binsize'] = binsize

        if header[1] == NNTSC_LIVE:
            name, stream_id, data = pickle.loads(self.buf[header_end:total_len])
            msgdict['collection'] = name
            msgdict['streamid'] = stream_id
            msgdict['data'] = data

        if header[1] == NNTSC_PUSH:
            colid, timestamp = pickle.loads(self.buf[header_end:total_len])
            msgdict['collection'] = colid
            msgdict['timestamp'] = timestamp

        if header[1] == NNTSC_QUERY_CANCELLED:
            request, data = pickle.loads(self.buf[header_end:total_len])
            msgdict['request'] = request

            if request == NNTSC_SCHEMAS:
                msgdict['colid'] = data

            if request in [NNTSC_STREAMS, NNTSC_ACTIVE_STREAMS]:
                msgdict['collection'] = data[0]
                msgdict['boundary'] = data[1]

            if request == NNTSC_HISTORY:
                collection, labels, start, end, more = data
                msgdict['collection'] = collection
                msgdict['start'] = start
                msgdict['end'] = end
                msgdict['more'] = more
                msgdict['labels'] = labels

        self.buf = self.buf[total_len:]
        return header[1], msgdict

    def convert_streams_to_labels(self, streams):

        labels = {}

        for s in streams:
            # XXX Make the labels strings, otherwise we run into casting
            # issues later on with Brendon's hax ampy code.
            labels[str(s)] = [s]
        return labels

# vim: set sw=4 tabstop=4 softtabstop=4 expandtab :
