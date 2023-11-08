#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Top Block
# GNU Radio version: 3.8.1.0

from gnuradio import blocks
from gnuradio import gr
from gnuradio.filter import firdes
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import zeromq
import subprocess

class top_block(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Top Block")

        ##################################################
        # Blocks
        ##################################################
        self.zeromq_req_source_2 = zeromq.req_source(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.2:2101', 100, False, -1)
        self.zeromq_req_source_1 = zeromq.req_source(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.4:2011', 100, False, -1)
        self.zeromq_req_source_0 = zeromq.req_source(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.3:2001', 100, False, -1)
        self.zeromaddNewUEq_rep_sink_2 = zeromq.rep_sink(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.2: 2010', 100, False, -1)
        self.zeromq_rep_sink_1 = zeromq.rep_sink(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.2: 2000', 100, False, -1)
        self.zeromq_rep_sink_0 = zeromq.rep_sink(gr.sizeof_gr_complex, 1, 'tcp://10.0.0.2: 2100', 100, False, -1)
        self.blocks_add_xx_0 = blocks.add_vcc(1)

        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_add_xx_0, 0), (self.zeromq_rep_sink_0, 0))
        self.connect((self.zeromq_req_source_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.zeromq_req_source_1, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.zeromq_req_source_2, 0), (self.zeromq_rep_sink_1, 0))
        self.connect((self.zeromq_req_source_2, 0), (self.zeromq_rep_sink_2, 0))



def main(top_block_cls=top_block, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    subprocess.run("tail -f /dev/null", shell=True) # keep alive

if __name__ == '__main__':
    main()