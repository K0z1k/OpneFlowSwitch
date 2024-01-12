#!/usr/bin/env python3
import argparse
import os
import sys
import json
from time import sleep

import grpc
from dataclasses import dataclass
from typing import List

# Import P4Runtime lib from parent utils dir
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '/home/p4/tutorials/utils/'))
import p4runtime_lib.bmv2
import p4runtime_lib.helper
from p4runtime_lib.error_utils import printGrpcError
from p4runtime_lib.switch import ShutdownAllSwitchConnections


"""
struct ofp_flow_mod {
struct ofp_header header;
uint64_t cookie; # Opaque controller-issued identifier.
uint64_t cookie_mask; # Mask used to restrict the cookie bits that must match when the command is OFPFC_MODIFY* or OFPFC_DELETE*. A value of 0 indicates no restriction.
uint8_t table_id; # ID of the table to put the flow in. For OFPFC_DELETE_* commands, OFPTT_ALL can also be used to delete matching flows from all tables.
uint8_t command; # One of OFPFC_*.
uint16_t idle_timeout; # Idle time before discarding (seconds).
uint16_t hard_timeout; # Max time before discarding (seconds).
uint16_t priority; # Priority level of flow entry.
uint32_t buffer_id; # Buffered packet to apply to, or OFP_NO_BUFFER. Not meaningful for OFPFC_DELETE*.
uint32_t out_port; # For OFPFC_DELETE* commands, require matching entries to include this as an output port. A value of OFPP_ANY indicates no restriction.
uint32_t out_group; # For OFPFC_DELETE* commands, require matching entries to include this as an output group. A value of OFPG_ANY indicates no restriction.
uint16_t flags; # Bitmap of OFPFF_* flags.
uint16_t importance; # Eviction precedence (optional).
struct ofp_match match; # Fields to match. Variable size.
/* The variable size and padded match is always followed by instructions.
//struct ofp_instruction_header instructions[0];
/* Instruction set - 0 or more. The length
of the instruction set is inferred from
the length field in the header. */
};
"""
"""
/* Fields to match against flows */
struct ofp_match {
uint16_t type; /* One of OFPMT_* */
uint16_t length; /* Length of ofp_match (excluding padding) */
/* Followed by:
* - Exactly (length - 4) (possibly 0) bytes containing OXM TLVs, then
* - Exactly ((length + 7)/8*8 - length) (between 0 and 7) bytes of
* all-zero bytes
* In summary, ofp_match is padded as needed, to make its overall size
* a multiple of 8, to preserve alignment in structures using it.
*/
uint8_t oxm_fields[0]; /* 0 or more OXM match fields */
uint8_t pad[4]; /* Zero bytes - see above for sizing */
};
OFP_ASSERT(sizeof(struct ofp_match) == 8);
"""
@dataclass
class ofp_instructions:
    instruction_type: str#uint16_t
    instruction_len: str #uint16_t
    actions : List[str]

@dataclass
class ofp_match:
    type: str #uint16_t
    length: str #uint16_t
    oxm_fields : List[str] #string


@dataclass
class OFP_message:
    cookie: str #unit64
    cookie_mask: str #uint64
    table_id: str #uint8_t
    command: str #uint8_t
    idle_timeout: str #uint16_t
    hard_timeout: str #uint16_t
    priority: str #uint16_t
    buffer_id: str #uint32_t
    out_port: str #uint32_t
    out_group: str #uint32_t
    flags: str #uint16_t
    match: ofp_match#ofp_match
    instructions: ofp_instructions #ofp_instruction_header

def writeTableRules(p4info_helper, sw, dst_eth_addr, dst_ip_addr, port, table):
    """

    :param p4info_helper: obiekt P4Info helper
    :param sw: polaczenie do switcha


    :param dst_eth_addr: docelowy adres MAC
    :param dst_ip_addr: docelowy adres IP

    """
    # 1) Zasada do wpisania do tabeli
    table_entry = p4info_helper.buildTableEntry(
        table_name= table,
        match_fields={
            "hdr.ipv4.dstAddr": (dst_ip_addr, 32)
        },
        action_name="MyIngress.ipv4_forward",
        action_params={
            "dstAddr": dst_eth_addr,
            "port": port
        })
    sw.WriteTableEntry(table_entry)
    print("Wpisano zasade to tabeli %s" % sw.name)


def readTableRules(p4info_helper, sw):
    """
    Odczytuje wszystkie wprowadzone zasady do tabeli w switch-u.

    :param p4info_helper: obiekt P4Info helper
    :param sw: polaczenie do switcha
    """
    print('\n----- Odczytywanie zasad dla tabeli %s -----' % sw.name)
    for response in sw.ReadTableEntries():
        for entity in response.entities:
            entry = entity.table_entry

            table_name = p4info_helper.get_tables_name(entry.table_id)
            print('%s: ' % table_name, end=' ')
            for m in entry.match:
                print(p4info_helper.get_match_field_name(table_name, m.field_id), end=' ')
                print('%r' % (p4info_helper.get_match_field_value(m),), end=' ')
            action = entry.action.action
            action_name = p4info_helper.get_actions_name(action.action_id)
            print('->', action_name, end=' ')
            for p in action.params:
                print(p4info_helper.get_action_param_name(action_name, p.param_id), end=' ')
                print('%r' % p.value, end=' ')
            print()

def printGrpcError(e):
    print("gRPC Error:", e.details(), end=' ')
    status_code = e.code()
    print("(%s)" % status_code.name, end=' ')
    traceback = sys.exc_info()[2]
    print("[%s:%d]" % (traceback.tb_frame.f_code.co_filename, traceback.tb_lineno))

def main(p4info_file_path, bmv2_file_path):
    # Stworzenie obiektu p4info_helper z przypisaniem sciezki do pliku p4info
    p4info_helper = p4runtime_lib.helper.P4InfoHelper(p4info_file_path)

    #print(p4info_file_path)


    #zaladowanie sparsowanej wiadomosci OpenFlow z pliku JSON
    with open('OFP_Message.json','r') as file:
        data = json.load(file)



    #Match = ofp_match(type = 1, length = 2, oxm_fields = ["ipv4_dst","24","10.0.3.3"]) # dlugosc, typ, [typ_pola,maska,wartosc]
    #Instructions = ofp_instructions(instruction_type = 3, instruction_len = 24, actions = ["16","65535","3","0"]) # dlugosc, typ, [dlugosc,maksymalna_dlugosc,port,typ]
    #Message = OFP_message(0,0,1,0,0,0,20,6535,4294967295,4294967295,0,Match,Instructions)

    # wpisanie parametrow z wiadomosci OpenFlow pod zmienne
    match_type = data["OFPFlowMod"]["match"]["OFPMatch"]["type"]
    match_length = data["OFPFlowMod"]["match"]["OFPMatch"]["length"]
    match = data["OFPFlowMod"]["match"]["OFPMatch"]
    for oxm_field in match["oxm_fields"]:
        oxm_field_1 = oxm_field["OXMTlv"]["field"]
        oxm_field_2 = oxm_field["OXMTlv"]["mask"]
        oxm_field_3 = oxm_field["OXMTlv"]["value"]
    oxm_fields = [oxm_field_1, oxm_field_2, oxm_field_3]

    instructions = data["OFPFlowMod"]["instructions"]
    for instruction in instructions:
        if  "OFPInstructionActions" in instruction:
            actions = instruction["OFPInstructionActions"]
            instruction_type = actions["type"]
            instruction_len = actions["len"]
            for action in actions["actions"]:
                if "OFPActionOutput" in action:
                    output_action = action["OFPActionOutput"]
                    actions_1 = output_action["len"]
                    actions_2 = output_action["max_len"]
                    actions_3 = output_action["port"]
                    actions_4 = output_action["type"]
    actions = [actions_1, actions_2, actions_3, actions_4]


    cookie = data["OFPFlowMod"]["cookie"]
    cookie_mask = data["OFPFlowMod"]["cookie_mask"]
    table_id = data["OFPFlowMod"]["table_id"]
    command = data["OFPFlowMod"]["command"]
    idle_timeout = data["OFPFlowMod"]["idle_timeout"]
    hard_timeout = data["OFPFlowMod"]["hard_timeout"]
    priority = data["OFPFlowMod"]["priority"]
    buffer_id = data["OFPFlowMod"]["buffer_id"]
    out_port = data["OFPFlowMod"]["out_port"]
    out_group = data["OFPFlowMod"]["out_group"]
    flags = data["OFPFlowMod"]["flags"]

    #wpisanie parametrow z wiadomosci do obiektow klas danych opisujacych elementy wiadomosci
    Match = ofp_match(type = match_type, length = match_length, oxm_fields = oxm_fields)

    Instructions = ofp_instructions(instruction_type = instruction_type, instruction_len = instruction_len, actions = actions)

    Message = OFP_message(cookie = cookie, cookie_mask = cookie_mask, table_id = table_id , command = command, idle_timeout = idle_timeout, hard_timeout = hard_timeout, priority = priority, buffer_id = buffer_id, out_port = out_port, out_group = out_group, flags = flags, match = Match, instructions = Instructions)

    table = ""
    mac_addr = ""
    port = 0


    if(Message.table_id == 1):                  #przetlumaczenie id z wiadomosci OFP na nazwe tabeli w P4
        table = "MyIngress.ipv4_lpm"

    else: print("nie ta tabela")




    if( Message.match.oxm_fields[2] == "10.0.3.3"):    #przetlumacznie docelowego adresu IP na na docelowy adres MAC
        mac_addr = "08:00:00:00:03:33"

    else: print("nie 3")

    try:
        # Utworzenie poloczenia do s1 dzieki gRPC oraz utworzenie logu z calosci przeslanych wiadomosci

        s1 = p4runtime_lib.bmv2.Bmv2SwitchConnection(
            name='s1',
            address='127.0.0.1:50051',
            device_id=0,
            proto_dump_file='requests-from-controler.txt')


        # Wyslanie  master arbitration update message do switcha aby ustawic  kontroler jako master (Wymagane przez P4Runtime aby prtzeprowadzic operacje zapisywania)
        s1.MasterArbitrationUpdate()



        print(mac_addr," ",Message.match.oxm_fields[2]," ",Message.instructions.actions[2]," ",table)

        #wpisanie zdefiniwanej zasady do tabeli
        writeTableRules(p4info_helper, sw=s1, dst_eth_addr=mac_addr, dst_ip_addr = Message.match.oxm_fields[2], port = Message.instructions.action[2], table = table)


        # odczytanie wartosci obecnych w tabeli
        #readTableRules(p4info_helper, s1)



    except KeyboardInterrupt:
        print(" Stop.")
    except grpc.RpcError as e:
        printGrpcError(e)

    ShutdownAllSwitchConnections()

if __name__ == '__main__':      #ustawienie zmiennych potrzbnych do dzialania kontrolera, p4info oraz opis switcha Simple_Switch
    parser = argparse.ArgumentParser(description='P4Runtime Controller')
    parser.add_argument('--p4info', help='p4info proto in text format from p4c',
                        type=str, action="store", required=False,
                        default='./build/Simple_Switch.p4.p4info.txt')
    parser.add_argument('--bmv2-json', help='BMv2 JSON file from p4c',
                        type=str, action="store", required=False,
                        default='./build/Simple_Switch.json')
    args = parser.parse_args()

    if not os.path.exists(args.p4info):
        parser.print_help()
        print("\np4info plik nie znaleziony: %s\n" % args.p4info)
        parser.exit(1)
    if not os.path.exists(args.bmv2_json):
        parser.print_help()
        print("\nBMv2 JSON plik nie znaleziony: %s\n" % args.bmv2_json)
        parser.exit(1)
    main(args.p4info, args.bmv2_json)
