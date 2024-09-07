#!/usr/bin/env python3
"""TS editor"""

import argparse
import struct

# CHUNK_SIZE = 10000
TS_PACKET_SIZE = 188

STREAM_ID_PROGRAM_STREAM_MAP = 0b10111100
STREAM_ID_PRIVATE_STREAM_1 = 0b10111101
STREAM_ID_PADDING_STREAM = 0b10111110
STREAM_ID_PRIVATE_STREAM_2 = 0b10111111
STREAM_ID_AUDIO_STREAM_0 = 0b11000000
STREAM_ID_VIDEO_STREAM_0 = 0b11100000
STREAM_ID_ECM_STREAM = 0b11110000
STREAM_ID_EMM_STREAM = 0b11110001
STREAM_ID_DSMCC_STREAM = 0b11110010
STREAM_ID_ISO_IEC_13522_STREAM = 0b11110011
STREAM_ID_TYPE_A_STREAM = 0b11110100
STREAM_ID_TYPE_B_STREAM = 0b11110101
STREAM_ID_TYPE_C_STREAM = 0b11110110
STREAM_ID_TYPE_D_STREAM = 0b11110111
STREAM_ID_TYPE_E_STREAM = 0b11111000
STREAM_ID_ANCILLARY_STREAM = 0b11111001
STREAM_ID_SL_PACKETIZED_STREAM = 0b11111010
STREAM_ID_FLEXMUX_STREAM = 0b11111011
STREAM_ID_METADATA_STREAM = 0b11111100
STREAM_ID_EXTENDED_STREAM_ID = 0b11111101
STREAM_ID_RESERVED_DATA_STREAM = 0b11111110
STREAM_ID_PROGRAM_STREAM_DIRECTORY = 0b11111111


def print_binaries(buffer, offset=0):
    """Print binaries."""
    NUM_BYTES = 8

    for i in range(0, len(buffer), NUM_BYTES):
        print(f'{i + offset:010X} | ', end='')
        j = min(i + NUM_BYTES, len(buffer))
        print(' '.join([f'{b:02X}' for b in buffer[i:j]]), end='')
        print(' | ', end='')
        print(''.join([f'{b:c}' for b in buffer[i:j]]))


def get_ts_packet(packet, packet_size):
    return packet[packet_size - TS_PACKET_SIZE :]


def get_sync_byte(ts_packet):
    return ts_packet[0]


def get_transport_error_indicator(ts_packet):
    return (ts_packet[1] & 0b10000000) >> 7


def get_payload_unit_start_indicator(ts_packet):
    return (ts_packet[1] & 0b01000000) >> 6


def get_transport_priority(ts_packet):
    return (ts_packet[1] & 0b00100000) >> 5


def get_pid(ts_packet):
    return struct.unpack('>H', ts_packet[1:3])[0] & 0b00011111_11111111


def get_transport_scrambling_control(ts_packet):
    return (ts_packet[3] & 0b11000000) >> 6


def get_adaptation_field_control(ts_packet):
    return (ts_packet[3] & 0b00110000) >> 4


def get_continuity_counter(ts_packet):
    return ts_packet[3] & 0b00001111


class AdaptationField:
    """Adaptation Field"""

    def __init__(self, field):
        self.adaptation_field_length = field[0]
        self.random_access_indicator = None
        self.pcr_flag = None
        self.opcr_flag = None
        self.pcr_base = None
        self.pcr_ext = None
        self.opcr_base = None
        self.opcr_ext = None
        if self.adaptation_field_length > 0:
            # TODO
            self.random_access_indicator = (field[1] & 0b01000000) >> 6
            # TODO
            self.pcr_flag = (field[1] & 0b00010000) >> 4
            self.opcr_flag = (field[1] & 0b00001000) >> 3
            # TODO
            offset = 0
            if self.pcr_flag == 1:
                self.pcr_base = struct.unpack('>I', field[2:6])[0] << 1 | field[6] & 0b10000000
                # Reserved
                self.pcr_ext = (field[6] & 0b00000001) << 8 | field[7]
                offset += 6
            if self.opcr_flag == 1:
                self.opcr_base = (
                    struct.unpack('>I', field[2 + offset : 6 + offset])[0] << 1 | field[6 + offset] & 0b10000000
                )
                # Reserved
                self.opcr_ext = (field[6 + offset] & 0b00000001) << 8 | field[7 + offset]
                offset += 6
            # TODO


def get_adaptation_field(ts_packet):
    adaptation_field_control = get_adaptation_field_control(ts_packet)
    if adaptation_field_control in (0b10, 0b11):
        adaptation_field = AdaptationField(ts_packet[4:])
    else:
        adaptation_field = None

    return adaptation_field


def get_payload(ts_packet):
    adaptation_field_control = get_adaptation_field_control(ts_packet)
    if adaptation_field_control in (0b10, 0b11):
        payload_offset = ts_packet[4] + 1
    else:
        payload_offset = 0
    if adaptation_field_control in (0b01, 0b11):
        payload = ts_packet[4 + payload_offset :]
    else:
        payload = None

    return payload


class Payload:
    def __init__(self):
        self.buffer = b''
        self.__payload = None

    def update(self, payload_unit_start_indicator, prev, next=None):
        if payload_unit_start_indicator == 1:
            if self.buffer:
                self.buffer += prev
                self.__payload = self.buffer

            self.buffer = next
        else:
            self.buffer += prev
            self.__payload = None

        return self.__payload


class Section(Payload):
    def __init__(self):
        super().__init__()
        self.section = None

    def update(self, ts_packet):
        payload_unit_start_indicator = get_payload_unit_start_indicator(ts_packet)
        payload = get_payload(ts_packet)
        if payload_unit_start_indicator == 1:
            pointer_field = payload[0]
            prev = payload[:pointer_field]
            next = payload[1 + pointer_field :]
            self.section = super().update(payload_unit_start_indicator, prev, next)
        else:
            prev = payload
            self.section = super().update(payload_unit_start_indicator, prev)


class Psi:
    """Program Specific Information Table"""

    def __init__(self, section):
        self.table_id = section[0]
        self.section_syntax_indicator = (section[1] & 0b10000000) >> 7
        # '0'
        # reserved
        self.section_length = struct.unpack('>H', section[1:3])[0] & 0b00001111_11111111
        # 2 bytes
        # reserved
        self.version_number = (section[5] & 0b00111110) >> 1
        self.current_next_indicator = section[5] & 0b00000001
        self.section_number = section[6]
        self.last_section_number = section[7]
        # Some bytes
        self.crc_32 = struct.unpack('>I', section[self.section_length - 1 : self.section_length + 3])[0]


class Pat(Psi):
    """Program Association Table"""

    def __init__(self, section):
        super().__init__(section)
        self.transport_stream_id = struct.unpack('>H', section[3:5])[0]

        num_programs = (self.section_length - 9) // 4
        self.program_numbers = [[] for _ in range(num_programs)]
        self.pids = [[] for _ in range(num_programs)]
        for i in range(num_programs):
            i_4 = i * 4
            self.program_numbers[i] = struct.unpack('>H', section[8 + i_4 : 10 + i_4])[0]
            # reserved
            # network_pid if program_numbers[i] == 0, program_map_pid otherwise
            self.pids[i] = struct.unpack('>H', section[10 + i_4 : 12 + i_4])[0] & 0b00011111_11111111


class Pmt(Psi):
    """Program Mapping Table"""

    def __init__(self, section):
        super().__init__(section)
        self.program_number = struct.unpack('>H', section[3:5])[0]

        # reserved
        self.pcr_pid = struct.unpack('>H', section[8:10])[0] & 0b00011111_11111111
        # reserved
        self.program_info_length = struct.unpack('>H', section[10:12])[0] & 0b00001111_11111111

        pos = 12
        self.descriptor = []
        while pos < 12 + self.program_info_length:
            length = 2 + section[pos + 1]
            self.descriptor += section[pos : pos + length]
            pos += length

        self.stream_types = []
        self.elementary_pids = []
        self.es_info_length = []
        self.stream_descriptors = []
        i = 0
        while pos < self.section_length - 1:
            self.stream_types += [section[pos]]
            # reserved
            self.elementary_pids += [struct.unpack('>H', section[pos + 1 : pos + 3])[0] & 0b00011111_11111111]
            # reserved
            self.es_info_length += [struct.unpack('>H', section[pos + 3 : pos + 5])[0] & 0b00001111_11111111]
            pos += 5
            pos_2 = pos
            self.stream_descriptors.append([])
            while pos_2 < pos + self.es_info_length[i]:
                length = 2 + section[pos_2 + 1]
                self.stream_descriptors[i] += section[pos_2 : pos_2 + length]
                pos_2 += length
            pos = pos_2
            i += 1


class Pes:
    """Packetized Elementary Stream"""

    def __init__(self, pes_payload):
        self.packet_start_code_prefix = (
            pes_payload[0] << 16 | pes_payload[1] << 8 | pes_payload[2] if 0x000001 else None
        )
        self.stream_id = None
        self.pes_packet_length = None
        self.pts_dts_flags = None
        self.pes_header_data_length = None
        self.pts = None
        self.dts = None
        self.pes_packet_data_byte = None
        if self.packet_start_code_prefix:
            self.stream_id = pes_payload[3]
            self.pes_packet_length = struct.unpack('>H', pes_payload[4:6])[0]
            if self.stream_id not in (
                STREAM_ID_PROGRAM_STREAM_MAP,
                STREAM_ID_PADDING_STREAM,
                STREAM_ID_PRIVATE_STREAM_2,
                STREAM_ID_ECM_STREAM,
                STREAM_ID_EMM_STREAM,
                STREAM_ID_PROGRAM_STREAM_DIRECTORY,
                STREAM_ID_DSMCC_STREAM,
                STREAM_ID_TYPE_E_STREAM,
            ):
                # TODO
                self.pts_dts_flags = (pes_payload[7] & 0b11000000) >> 6
                # TODO
                self.pes_header_data_length = pes_payload[8]
                if self.pts_dts_flags in (0b10, 0b11):
                    # '001x'
                    pts_32 = pes_payload[9] & 0b00001110
                    # marker_bit
                    pts_29 = struct.unpack('>H', pes_payload[10:12])[0] & 0b11111111_11111110
                    # marker_bit
                    pts_14 = struct.unpack('>H', pes_payload[12:14])[0] & 0b11111111_11111110
                    # marker_bit
                    self.pts = pts_32 << 29 | pts_29 << 14 | pts_14 >> 1
                    if self.pts_dts_flags == 0b11:
                        # '0001'
                        dts_32 = pes_payload[14] & 0b00001110
                        # marker_bit
                        dts_29 = struct.unpack('>H', pes_payload[15:17])[0] & 0b11111111_11111110
                        # marker_bit
                        dts_14 = struct.unpack('>H', pes_payload[17:19])[0] & 0b11111111_11111110
                        # marker_bit
                        self.dts = dts_32 << 29 | dts_29 << 14 | dts_14 >> 1
                # TODO
                self.pes_packet_data_byte = pes_payload[9 + self.pes_header_data_length :]
                # TODO


class Stream(Payload):
    def __init__(self):
        super().__init__()
        self.stream = None

    def update(self, ts_packet):
        payload_unit_start_indicator = get_payload_unit_start_indicator(ts_packet)
        payload = get_payload(ts_packet)
        if payload_unit_start_indicator == 1:
            prev = b''
            next = Pes(payload).pes_packet_data_byte
            self.stream = super().update(payload_unit_start_indicator, prev, next)
        else:
            prev = payload
            self.stream = super().update(payload_unit_start_indicator, prev)


def get_picture_coding_type(pes_stream):
    picture_start_code = 0x00000100
    picture_coding_types = {0b001: 'I', 0b010: 'P', 0b011: 'B'}

    i = 0
    while i + 3 < len(pes_stream):
        if struct.unpack('>I', pes_stream[i : i + 4])[0] == picture_start_code:
            return picture_coding_types[(pes_stream[i + 5] & 0b00111000) >> 3]
        else:
            i += 1


def packets(args):
    """Show packet info."""
    with open(args.infile, 'rb') as tsi:
        offset = 0
        packet_idx = 0
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)
            offset += args.packet_size - TS_PACKET_SIZE

            # Resync
            # while get_sync_byte(ts_packet) != 0x47:
            #     ts_packet = ts_packet[1:] + tsi.read(1)
            #     offset += 1

            pid = get_pid(ts_packet)
            print('{:012d} [0x{:04X}]'.format(offset, pid))
            offset += TS_PACKET_SIZE

            packet_idx += 1


def pid(args):
    """Show pid info."""
    with open(args.infile, 'rb') as tsi:
        pids = []
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)

            pid = get_pid(ts_packet)
            pids.append(pid)

    elements = set(pids)
    for i in range(0x1FFF):
        if i in elements:
            print('[0x{:04X}] {:12d}'.format(i, pids.count(i)))


def programs(args):
    """Show program info."""
    with open(args.infile, 'rb') as tsi:
        pat_section = Section()
        program_map_pids = []
        pat_loaded = False
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)

            pid = get_pid(ts_packet)
            if pid == 0x0000 and not pat_loaded:  # Only the first PAT is used now
                # Program Association Table
                pat_section.update(ts_packet)
                if pat_section.section:
                    pat = Pat(pat_section.section)
                    program_map_pids = [p for i, p in enumerate(pat.pids) if pat.program_numbers[i] != 0]
                    program_numbers = [p for i, p in enumerate(pat.program_numbers) if pat.program_numbers[i] != 0]
                    pat_loaded = True

                    pmt_section = [Section() for _ in range(len(program_map_pids))]
                    elementary_pids = [[] for _ in range(len(program_map_pids))]
                    stream_types = [[] for _ in range(len(program_map_pids))]
            elif pid in program_map_pids:
                # Program Map Table
                i = program_map_pids.index(pid)
                pmt_section[i].update(ts_packet)
                if pmt_section[i].section:
                    pmt = Pmt(pmt_section[i].section)
                    # Append only new elements
                    for p, t in zip(pmt.elementary_pids, pmt.stream_types):
                        if p not in elementary_pids[i]:
                            elementary_pids[i].append(p)
                            stream_types[i].append(t)

    for i in range(len(program_map_pids)):
        print('Program {}[0x{:04X}]'.format(program_numbers[i], program_map_pids[i]))
        for j in range(len(elementary_pids[i])):
            print('  Stream [0x{:04X}]: '.format(elementary_pids[i][j]), end='')
            print('type [0x{:04X}]'.format(stream_types[i][j]))


def frames(args):
    """Show frame info."""
    with open(args.infile, 'rb') as tsi:
        # Determine the video pid
        pat_section = Section()
        program_1_pid = None
        pmt_section = Section()
        video_pid = None
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)

            pid = get_pid(ts_packet)
            if pid == 0x0000:
                # Program Association Table
                pat_section.update(ts_packet)
                if pat_section.section:
                    pat = Pat(pat_section.section)
                    program_1_pid = pat.pids[1]  # Only the first program is used
            elif pid == program_1_pid:
                # Program Map Table
                pmt_section.update(ts_packet)
                if pmt_section.section:
                    pmt = Pmt(pmt_section.section)
                    video_pid = pmt.elementary_pids[
                        pmt.stream_types.index(0x02)
                    ]  # Only the first video stream is used
                    break

        tsi.seek(0)
        video_stream = Stream()
        pts = None
        # hoge = None
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)
            # if not hoge:
            #     hoge = (struct.unpack('>I', packet[:4])[0] << 2) >> 2
            # print((((struct.unpack('>I', packet[:4])[0] << 2) >> 2) - hoge) / 1356)

            pid = get_pid(ts_packet)
            if pid == video_pid:
                # Video PES
                video_stream.update(ts_packet)
                if video_stream.stream:
                    picture_coding_type = get_picture_coding_type(video_stream.stream)
                    if pts:
                        print(f'{pts:.6f},{picture_coding_type}')

                    video_pes = Pes(get_payload(ts_packet))
                    if video_pes.pts:
                        pts = video_pes.pts / 90000
                    # if video_pes.dts:
                    #     print(video_pes.dts)
        # Print the last frame
        picture_coding_type = get_picture_coding_type(video_stream.buffer)
        print(f'{pts:.6f},{picture_coding_type}')


def cut(args):
    """Trim a ts file."""
    with open(args.infile, 'rb') as tsi, open(args.outfile, 'wb') as tso:
        # Determine the video pid
        pat_section = Section()
        program_1_pid = None
        pmt_section = Section()
        video_pid = None
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)

            pid = get_pid(ts_packet)
            if pid == 0x0000:
                # Program Association Table
                pat_section.update(ts_packet)
                if pat_section.section:
                    pat = Pat(pat_section.section)
                    program_1_pid = pat.pids[1]  # Only the first program is used
            elif pid == program_1_pid:
                # Program Map Table
                pmt_section.update(ts_packet)
                if pmt_section.section:
                    pmt = Pmt(pmt_section.section)
                    video_pid = pmt.elementary_pids[
                        pmt.stream_types.index(0x02)
                    ]  # Only the first video stream is used
                    break

        tsi.seek(0)
        packet_idx = 0
        packet_idx_prev = None
        video_stream = Stream()
        pts = None
        offset = 0
        is_set = False
        inpoint = 0
        outpoint = None
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            ts_packet = get_ts_packet(packet, args.packet_size)

            pid = get_pid(ts_packet)
            if pid == video_pid:
                # Video PES
                video_stream.update(ts_packet)
                if video_stream.stream:
                    picture_coding_type = get_picture_coding_type(video_stream.stream)
                    if pts:
                        if args.relative_time:
                            if not is_set and picture_coding_type == 'I':
                                offset = pts
                                is_set = True
                        if pts < args.start + offset and picture_coding_type == 'I':
                            inpoint = packet_idx_prev
                        if args.end + offset < pts and picture_coding_type == 'I':
                            outpoint = packet_idx
                            break

                    video_pes = Pes(get_payload(ts_packet))
                    if video_pes.pts:
                        pts = video_pes.pts / 90000
                        packet_idx_prev = packet_idx

            packet_idx += 1
        if not outpoint:
            outpoint = packet_idx

        tsi.seek(inpoint * args.packet_size)
        tso.write(tsi.read((outpoint - inpoint) * args.packet_size))


def get_video_pid(tsi, packet_size):
    """Determine the video pid"""
    tsi.seek(0)
    pat_section = Section()
    program_1_pid = None
    pmt_section = Section()
    video_pid = None
    for packet in iter(lambda: tsi.read(packet_size), b''):
        ts_packet = get_ts_packet(packet, packet_size)

        pid = get_pid(ts_packet)
        if pid == 0x0000:
            # Program Association Table
            pat_section.update(ts_packet)
            if pat_section.section:
                pat = Pat(pat_section.section)
                program_1_pid = pat.pids[1]  # Only the first program is used
        elif pid == program_1_pid:
            # Program Map Table
            pmt_section.update(ts_packet)
            if pmt_section.section:
                pmt = Pmt(pmt_section.section)
                video_pid = pmt.elementary_pids[pmt.stream_types.index(0x02)]  # Only the first video stream is used
                break

    return video_pid


def get_edge_timestamp(tsi, packet_size, isLast=False):
    video_pid = get_video_pid(tsi, packet_size)

    tsi.seek(0)
    pcr_edge = None
    pts_edge = None
    dts_edge = None
    for packet in iter(lambda: tsi.read(packet_size), b''):
        ts_packet = get_ts_packet(packet, packet_size)

        af = get_adaptation_field(ts_packet)
        if af:
            if af.pcr_base:
                pcr_edge = af.pcr_base * 300 + af.pcr_ext if isLast or not pcr_edge else pcr_edge

        pid = get_pid(ts_packet)
        if pid == video_pid:
            if get_payload_unit_start_indicator(ts_packet) == 1:
                video_pes = Pes(get_payload(ts_packet))
                if video_pes.pts:
                    pts_edge = video_pes.pts if isLast or not pts_edge else pts_edge
                if video_pes.dts:
                    dts_edge = video_pes.dts if isLast or not dts_edge else dts_edge

        if not isLast:
            if pcr_edge and pts_edge and dts_edge:
                break

    return pcr_edge, pts_edge, dts_edge


def concat(args):
    """Concatenate two ts files."""
    with open(args.infile_1, 'rb') as tsi_1, open(args.infile_2, 'rb') as tsi_2, open(args.outfile, 'wb') as tso:
        # Find the last pts of infile_1
        _, pts_last, _ = get_edge_timestamp(tsi_1, args.packet_size, True)
        print(f'{pts_last/90000:.6f}')

        # Find the first pts of infile_2
        _, pts_first, _ = get_edge_timestamp(tsi_2, args.packet_size)
        print(f'{pts_first/90000:.6f}')
        print(f'{(pts_last - pts_first)/90000:.6f}')

        video_pid_2 = get_video_pid(tsi_2, args.packet_size)

        inpoint = 0
        diff = (pts_last - pts_first) / 90000
        if 0 < diff and diff < 2:
            tsi_2.seek(0)
            packet_idx = 0
            # video_stream = Stream()
            pts = None
            is_in = False
            for packet in iter(lambda: tsi_2.read(args.packet_size), b''):
                ts_packet = get_ts_packet(packet, args.packet_size)

                pid = get_pid(ts_packet)
                if pid == video_pid_2:
                    if get_payload_unit_start_indicator(ts_packet) == 1:
                        video_pes = Pes(get_payload(ts_packet))
                        if video_pes.pts:
                            pts = video_pes.pts
                            if pts == pts_last:
                                is_in = True
                else:
                    if is_in:
                        inpoint = packet_idx
                        break

                packet_idx += 1

        tsi_1.seek(0)
        tso.write(tsi_1.read())
        tsi_2.seek(inpoint * args.packet_size)
        tso.write(tsi_2.read())


def main():
    """Main routine"""
    parser = argparse.ArgumentParser(description='Process MPEG-TS files.')
    subparsers = parser.add_subparsers(required=True, help='subcommands')

    # command "packets"
    parser_packets = subparsers.add_parser('packets', aliases=['pkt'], help='show packet info')
    parser_packets.add_argument('infile', metavar='input', help='input file')
    parser_packets.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_packets.set_defaults(func=packets)

    # command "pid"
    parser_pid = subparsers.add_parser('pid', help='show pid info')
    parser_pid.add_argument('infile', metavar='input', help='input file')
    parser_pid.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_pid.set_defaults(func=pid)

    # command "programs"
    parser_programs = subparsers.add_parser('programs', aliases=['prg'], help='show program info')
    parser_programs.add_argument('infile', metavar='input', help='input file')
    parser_programs.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_programs.set_defaults(func=programs)

    # command "frames"
    parser_frames = subparsers.add_parser('frames', aliases=['frm'], help='show frame info')
    parser_frames.add_argument('infile', metavar='input', help='input file')
    parser_frames.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_frames.set_defaults(func=frames)

    # command "cut"
    parser_cut = subparsers.add_parser('cut', help='trim a ts file')
    parser_cut.add_argument(
        'infile',
        metavar='input',  # nargs='+',
        help='input file',
    )
    parser_cut.add_argument(
        'outfile',
        metavar='output',  # nargs='*',
        help='output file',
    )
    parser_cut.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_cut.add_argument('-r', '--relative-time', action='store_true', help='use relative time instead of PTS')
    parser_cut.add_argument('-s', '--start', type=float, default=0, help='start time [s]')
    parser_cut.add_argument('-e', '--end', type=float, default=60 * 60 * 24, help='end time [s]')
    parser_cut.set_defaults(func=cut)

    # command "concat"
    parser_concat = subparsers.add_parser('concat', help='concatenate two ts files')
    parser_concat.add_argument(
        'infile_1',
        metavar='input1',
        help='input file 1',
    )
    parser_concat.add_argument(
        'infile_2',
        metavar='input2',
        help='input file 2',
    )
    parser_concat.add_argument(
        'outfile',
        metavar='output',
        help='output file',
    )
    parser_concat.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192], default=188, help='TS packet size'
    )
    parser_concat.set_defaults(func=concat)

    args = parser.parse_args()
    args.func(args)


def main_old():
    """Main routine"""
    parser = argparse.ArgumentParser(description='Process MPEG-TS files.')
    parser.add_argument(
        'infile',
        metavar='input',  # nargs='+',
        help='input file',
    )
    parser.add_argument(
        'outfile',
        metavar='output',  # nargs='*',
        help='output file',
    )
    parser.add_argument(
        '-t', '--type', dest='packet_size', type=int, choices=[188, 192, 204], default=188, help='TS packet size'
    )
    parser.add_argument('-s', '--start', type=float, default=0, help='start time [s]')
    parser.add_argument('-e', '--end', type=float, default=60 * 60 * 24, help='end time [s]')
    args = parser.parse_args()

    # buffer_size = args.packet_size * CHUNK_SIZE

    with open(args.infile, 'rb') as tsi, open(args.outfile, 'wb') as tso:
        # buffer = [[] for _ in range(buffer_size)]
        pat_section = []
        program_1_pid = None
        # pat_packet = {}
        pmt_section = []
        video_pid = None
        audio_pid = None
        packet_idx = 0
        is_in = False
        # hoge = 0
        for packet in iter(lambda: tsi.read(args.packet_size), b''):
            # buffer[0:buffer_size - args.packet_size] = buffer[args.packet_size:]
            # buffer[buffer_size - args.packet_size:] = packet

            # if hoge != 0: print(struct.unpack('>I', packet[:4])[0] - hoge)
            ts_packet = packet[args.packet_size - TS_PACKET_SIZE :]

            # Transport Packet
            sync_byte = ts_packet[0]
            transport_error_indicator = (ts_packet[1] & 0b10000000) >> 7
            payload_unit_start_indicator = (ts_packet[1] & 0b01000000) >> 6
            transport_priority = (ts_packet[1] & 0b00100000) >> 5
            pid = struct.unpack('>H', ts_packet[1:3])[0] & 0b00011111_11111111
            transport_scrambling_control = (ts_packet[3] & 0b11000000) >> 6
            adaptation_field_control = (ts_packet[3] & 0b00110000) >> 4
            continuity_counter = ts_packet[3] & 0b00001111
            if adaptation_field_control in (0b10, 0b11):
                af = AdaptationField(ts_packet[4:])
                payload_offset = af.adaptation_field_length + 1
            else:
                af = None
                payload_offset = 0
            if adaptation_field_control in (0b01, 0b11):
                payload = ts_packet[4 + payload_offset :]
            else:
                payload = None

            # Adaptation Field
            # if af:
            #     if af.pcr_base:
            #         print(packet_idx, end='  ')
            #         print(' PCR', end=' ')
            #         print((af.pcr_base * 300 + af.pcr_ext)/27000000)
            #     if af.opcr_base:
            #         print(packet_idx, end='  ')
            #         print('OPCR', end=' ')
            #         print((af.opcr_base * 300 + af.opcr_ext)/27000000)

            # print(packet_idx, pid)
            if pid == 0x0000:
                # Program Association Table
                if payload_unit_start_indicator == 1:
                    pointer_field = payload[0]
                    if pat_section:
                        pat_section += payload[:pointer_field]
                        pat = Pat(pat_section)
                        program_1_pid = pat.pids[1]

                    pat_section = payload[1 + pointer_field :]
                    # pat_packet = {packet_idx, packet}
                else:
                    pat_section += payload
                    # pat_packet[packet_idx] = packet
            elif pid == program_1_pid:
                # Program Map Table
                if payload_unit_start_indicator == 1:
                    pointer_field = payload[0]
                    if pmt_section:
                        pmt_section += payload[:pointer_field]
                        pmt = Pmt(pmt_section)
                        video_pid = pmt.elementary_pids[pmt.stream_types.index(0x02)]
                        audio_pid = pmt.elementary_pids[pmt.stream_types.index(0x0F)]

                    pmt_section = payload[1 + pointer_field :]
                else:
                    pmt_section += payload
            elif pid == video_pid:
                # Video PES
                if payload_unit_start_indicator == 1:
                    video_pes = Pes(payload)
                    if video_pes.pts:
                        print(packet_idx, end=' V')
                        print(' PTS', end=' ')
                        print(video_pes.pts / 90000)
                        is_in = False
                        if (video_pes.pts / 90000 - args.start) > -1001 / 1000 / 60:
                            if video_pes.pts / 90000 < args.end:
                                is_in = True
                    # if video_pes.dts:
                    #     print(packet_idx, end=' V')
                    #     print(' DTS', end=' ')
                    #     print(video_pes.dts/90000)
            elif pid == audio_pid:
                # Audio PES
                if payload_unit_start_indicator == 1:
                    audio_pes = Pes(payload)
                    # if audio_pes.pts:
                    #     print(packet_idx, end=' A')
                    #     print(' PTS', end=' ')
                    #     print(audio_pes.pts/90000)

            if is_in:
                tso.write(packet)

            # hoge = struct.unpack('>I', packet[:4])[0]
            packet_idx += 1


if __name__ == '__main__':
    main()
