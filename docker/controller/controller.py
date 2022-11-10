#
# Copyright (C) 2022 Alexandre Mitsuru Kaihara
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import DEAD_DISPATCHER, MAIN_DISPATCHER, CONFIG_DISPATCHER, HANDSHAKE_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ether_types, ipv4, icmp, tcp, udp, in_proto
from ryu import utils
import pandas as pd
import datetime as date


# Variaveis para teste de sistema
TIME_LAST_PACKET = date.datetime.now()
feedback = pd.DataFrame(columns=['Duration', 'Flows', 'Packets', 'Packets desvio', 'Bytes', 'Teste'])
sleep_tests = [1.5, 1, 0.5, 0.25, 0.1, 0.05, 0.01, 0.001]
sleep_index = 0
# Variaveis para teste de sistema

class SimpleSwitch(app_manager.RyuApp):
        OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

        def __init__(self, *args, **kwargs):
                super(SimpleSwitch, self).__init__(*args, **kwargs)
                self.datapaths   = {}
                self.mac_to_port = {}
                self.delays = pd.DataFrame(columns = ["Timestamp", "Delay"])
                self.flows  = pd.DataFrame(columns = ['Date first seen', 'Duration', 'Proto', 'Src IP Addr', 
                                                     'Src Pt', 'Dst IP Addr', 'Dst Pt', 'Packets', 'Bytes', 
                                                     'Flows', 'Flags', 'Tos', 'class', 'attackType', 'attackID', 
                                                     'attackDescription'])
                self.current_flows = pd.DataFrame(columns = ['Datapath ID', 'Proto', 'Src IP Addr', 'Src Pt', 'Dst IP Addr', 'Dst Pt', "Datapaths"])

        @set_ev_cls(ofp_event.EventOFPErrorMsg,[HANDSHAKE_DISPATCHER, CONFIG_DISPATCHER, MAIN_DISPATCHER])
        def error_msg_handler(self, ev):
                msg = ev.msg
                self.logger.debug('OFPErrorMsg received: type=0x%02x code=0x%02x '
                        'message=%s',
                        msg.type, msg.code, utils.hex_array(msg.data))

        def add_flow(self, datapath, priority, match, actions, buffer_id = None, hard_tout = 0, inst = None, 
                     idle_tout = 0):
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                if inst == None:
                        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
                if buffer_id:
                        mod = parser.OFPFlowMod(datapath = datapath, buffer_id = buffer_id, priority = priority, 
                                                match = match, instructions = inst, hard_timeout = hard_tout, 
                                                idle_timeout = idle_tout, flags = ofproto.OFPFF_SEND_FLOW_REM)
                else:
                        mod = parser.OFPFlowMod(datapath = datapath, priority = priority, match = match, 
                                                instructions = inst, hard_timeout = hard_tout, 
                                                idle_timeout = idle_tout, flags = ofproto.OFPFF_SEND_FLOW_REM)
                datapath.send_msg(mod)
        
        @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
        def switch_features_handler(self, ev):
                datapath = ev.msg.datapath
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser

                match = parser.OFPMatch()
                actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
                self.add_flow(datapath, 0, match, actions)
        
        @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
        def _state_change_handler1(self, ev):
                datapath = ev.datapath
                if ev.state == MAIN_DISPATCHER:
                        if datapath.id not in self.datapaths:
                                self.logger.info("Register datapath: %016x", datapath.id)
                                self.datapaths[datapath.id] = datapath

                elif ev.state == DEAD_DISPATCHER:
                        if datapath.id in self.datapaths:
                                self.logger.info("Unregister datapath: %016x", datapath.id)
                                del self.datapaths[datapath.id]

        @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
        def _packet_in_handler(self, ev):
                msg = ev.msg
                datapath = msg.datapath
                ofproto  = datapath.ofproto
                parser = datapath.ofproto_parser
                pkt  = packet.Packet(msg.data)
                eth  = pkt.get_protocols(ethernet.ethernet)[0]
                dst  = eth.dst
                src  = eth.src
                dpid = datapath.id
                in_port = msg.match['in_port']
        
                # LLDP type will not be supported
                if eth.ethertype == ether_types.ETH_TYPE_LLDP:
                        return

                # Register the packet outport to learn the where it should be fowarded
                self.mac_to_port.setdefault(dpid, {})
                self.logger.info("packet in %s %s %s %s", dpid, src, dst, in_port)
                self.mac_to_port[dpid][src] = in_port

                # If the dst is known, just foward the package to the right outport
                if dst in self.mac_to_port[dpid]:
                        out_port = self.mac_to_port[dpid][dst]
                # If not, flood all nodes
                else:
                        out_port = ofproto.OFPP_FLOOD
                actions = [datapath.ofproto_parser.OFPActionOutput(out_port)]

                # Register flow and make action, if is not the case of flooding
                now = date.datetime.now().strftime("%Y-%m-%d %H:%M:%S:%f")
                # If the package is IP
                proto = ""
                if eth.ethertype == ether_types.ETH_TYPE_IP and out_port != ofproto.OFPP_FLOOD:
                        ipv4_pkt = pkt.get_protocol(ipv4.ipv4)
                        srcip = ipv4_pkt.src
                        dstip = ipv4_pkt.dst
                        tos = ipv4_pkt.tos
                        protocol = ipv4_pkt.proto
                        dstpt = 0
                        srcpt = 0
                        flags = "......"

                        # If the protocol is ICMP
                        if protocol == in_proto.IPPROTO_ICMP:
                                proto = "ICMP"
                                match = parser.OFPMatch(eth_type = ether_types.ETH_TYPE_IP, 
                                                        ipv4_src = srcip, ipv4_dst = dstip, 
                                                        ip_proto = protocol)
                
                        # If the protocol is TCP
                        elif protocol == in_proto.IPPROTO_TCP:
                                t = pkt.get_protocol(tcp.tcp)
                                flags = TCP_flags_to_string(t)
                                dstpt = t.dst_port
                                srcpt = t.src_port
                                proto = "TCP"
                                match = parser.OFPMatch(eth_type = ether_types.ETH_TYPE_IP, 
                                                        ipv4_src = srcip, ipv4_dst = dstip, 
                                                        ip_proto = protocol, tcp_src = srcpt, 
                                                        tcp_dst = dstpt)
                        # If the protocol is UDP
                        elif protocol == in_proto.IPPROTO_UDP:
                                u = pkt.get_protocol(udp.udp)
                                dstpt = u.dst_port
                                srcpt = u.src_port
                                proto = "UDP"
                                match = parser.OFPMatch(eth_type = ether_types.ETH_TYPE_IP, 
                                                        ipv4_src = srcip, ipv4_dst = dstip, 
                                                        ip_proto = protocol, udp_src = srcpt, 
                                                        udp_dst = dstpt)

                # If it is not ETH_TYPE_IP protocol
                else:
                        match = datapath.ofproto_parser.OFPMatch(eth_type = 2054, in_port = in_port, 
                                                                        eth_dst = dst)

                # If the buffe_id was set and it is not flood, add flow with this parameter
                if out_port != ofproto.OFPP_FLOOD:
                        if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                                self.add_flow(datapath, 1, match, actions, msg.buffer_id, idle_tout = 2)
                                return
                        else:
                                self.add_flow(datapath, 1, match, actions, idle_tout = 2)
                        #print("A flow has been added to the table")

                # If was a ipv4 packet
                if proto != "":
                        print("Datefirstseen =", now, "SrcIPAddr =", srcip, 
                                        "SrcPt =", srcpt, "DstIPAddr =", dstip, 
                                        "DstPt =", dstpt, "Proto =", proto, "Tos =", tos, 
                                        "Flags =", flags, "Datapath =", dpid, "Outport =", out_port)
                        
                data = None
                if msg.buffer_id == ofproto.OFP_NO_BUFFER:
                        data = msg.data

                out = datapath.ofproto_parser.OFPPacketOut(datapath = datapath, buffer_id = msg.buffer_id, 
                                                           in_port = in_port, actions = actions, data = data)
                datapath.send_msg(out)

        @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
        def _port_status_handler(self, ev):
                msg = ev.msg
                reason = msg.reason
                port_no = msg.desc.port_no
                ofproto = msg.datapath.ofproto
                if reason == ofproto.OFPPR_ADD:
                        self.logger.info("port added %s", port_no)
                elif reason == ofproto.OFPPR_DELETE:
                        self.logger.info("port deleted %s", port_no)
                elif reason == ofproto.OFPPR_MODIFY:
                        self.logger.info("port modified %d", port_no)
                else:
                        self.logger.info("illeagal port state %s %s", reason)

def TCP_flags_to_string(pkt):
        flags = [tcp.TCP_URG, tcp.TCP_ACK, tcp.TCP_PSH, tcp.TCP_RST, tcp.TCP_SYN, tcp.TCP_FIN]
        letters = ['U', 'A', 'P', 'R', 'S', 'F']
        fstr = "......"

        for i in range(0, len(flags)):
                if flags[i] == True:
                        aux    = list(fstr)
                        aux[i] = letters[i]
                        fstr   = "".join(aux)
        return fstr


def flow_to_csv(columns, flows, name):
        aux = pd.DataFrame(columns = [])
        for col in columns:
                aux[col] = list(flows[col])

        aux.to_csv(name, index = False, header = True)


def select_col(columns, flows, name):
        aux = pd.DataFrame(columns = [])
        for col in columns:
                aux[col] = list(flows[col])
        return aux


# Verifies the current counting against the real flow (subtraction of real - counting)
def check_counting(dataframe, path):
        flows = pd.read_csv(path)
        for i in range(dataframe.shape[0]):
                row = dataframe.loc[i]
                flowindex = flows.index[(flows['Dst Pt'] == float(row['Dst Pt'])) &
                                    (flows['Src Pt'] == float(row['Src Pt'])) &
                                    (flows['Src IP Addr'] == row['Src IP Addr']) &
                                    (flows['Dst IP Addr'] == row['Dst IP Addr'])]
                if len(flowindex) == 1:
                        row2 = flows.loc[flowindex]
                        row2['Duration'] -= row['Duration']
                        row2['Packets' ] -= row['Packets' ]
                        row2['Bytes'   ] -= row['Bytes'   ]
                        row2['Flows'   ] -= row['Flows'   ] 
                        flows.loc[flowindex] = row2
        return flows
