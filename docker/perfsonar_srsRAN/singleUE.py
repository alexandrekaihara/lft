#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# GNU Radio version: 3.8.1.0

from gnuradio import gr
from gnuradio.filter import firdes
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import zeromq

class single_ue(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet")

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 23040000

        ##################################################
        # Blocks
        ##################################################
        self.zeromq_req_source_ue = zeromq.req_source(gr.sizeof_gr_complex, 1, 'tcp://11.0.0.2:2001', 100, False, -1)
        self.zeromq_req_source_enb = zeromq.req_source(gr.sizeof_gr_complex, 1, 'tcp://11.0.0.1:2101', 100, False, -1)
        self.zeromq_rep_sink_enb = zeromq.rep_sink(gr.sizeof_gr_complex, 1, 'tcp://11.0.0.1:2100', 100, False, -1)
        self.zeromq_rep_sink_ue = zeromq.rep_sink(gr.sizeof_gr_complex, 1, 'tcp://11.0.0.1:2000', 100, False, -1)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.zeromq_req_source_enb, 0), (self.zeromq_rep_sink_ue, 0))
        self.connect((self.zeromq_req_source_ue, 0), (self.zeromq_rep_sink_enb, 0))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate



def main(top_block_cls=single_ue, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
