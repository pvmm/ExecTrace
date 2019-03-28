#!/usr/bin/env python
import sys

from exec_trace import ExecTrace

OUTPUT_DIR = "output"
romset_dir = None

KNOWN_VARS = {}
KNOWN_SUBROUTINES = {
  0x0047: ("WRTVDP", "Writes to the VDP register."),
  0x0093: ("WRTPSG", "Writes data to the PSG register."),
  0x0096: ("RDPSG", "Read data from the PSG register."),
  0x0138: ("RSLREG", "Reads the current output to the primary slot register."),
  0x013B: ("WSLREG", "Writes to the primary slot register."),
  0x013E: ("RDVDP", "Reads the VPD status register."),
  0x0141: ("SNSMAT", "Returns the status of a specified row of a keyboard matrix."),
}

def getVariableName(addr):
  if addr in KNOWN_VARS.keys():
    return KNOWN_VARS[addr]
  else:
    return "0x%04X" % addr

def get_subroutine_comment(addr):
  if addr in KNOWN_SUBROUTINES.keys():
    return KNOWN_SUBROUTINES[addr][1]

def get_label(addr):
  if addr in KNOWN_SUBROUTINES.keys():
    return KNOWN_SUBROUTINES[addr][0]
  elif addr < 0x4000:
    sys.exit("Unknown BIOS call: %04X" % addr)
  else:
    return "LABEL_%04X" % addr

class MSX_Trace(ExecTrace):
  def output_disasm_headers(self):
    header = "; Generated by MSX_ExecTrace\n"
    for var in KNOWN_VARS.keys():
      name = KNOWN_VARS[var]
      header += "%s\t\tEQU 0x%02X\n" % (name, var)
    return header

  def disasm_instruction(self, opcode):

    simple_instructions = {
      0x00: "nop",
      #0x02: "ld (bc), a",
      #0x03: "inc bc",
      #0x04: "inc b",
      0x07: "rlca",
      0x08: "ex af, af'",
      0x0f: "rrca",
      0x12: "ld (de), a",
      0x17: "rla",
      0x1f: "rra",
      0x2f: "cpl",
      0xeb: "ex de, hl",
      0xf9: "ld sp, hl", # TODO: This may be used to change exec flow by changing the ret address in the stack
      0xfb: "ei",
    }

    if opcode in simple_instructions:
      return simple_instructions[opcode]

    elif opcode & 0xCF == 0x01: # ld reg16, word
      STR = ['bc', 'de', 'hl', 'sp']
      imm = self.fetch()
      imm = imm | (self.fetch() << 8)
      return "ld %s, 0x%04X" % (STR[(opcode >> 4) & 3], imm)

    elif opcode & 0xCF == 0x03: # inc reg16
      STR = ['bc', 'de', 'hl', 'sp']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x04: # inc reg8
      STR = ['b', 'd', 'h', '(hl)']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x06: # ld _8, byte
      STR = ['b', 'd', 'hl', '(hl)']
      imm = self.fetch()
      return "ld %s, 0x%02X" % (STR[(opcode >> 4) & 3], imm)

    elif opcode & 0xCF == 0x09: # add hl, reg16 
      STR = ['bc', 'de', 'hl', 'sp']
      return "add hl, %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0C: # inc reg8
      STR = ['c', 'e', 'l', 'a']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0D: # dec reg8
      STR = ['c', 'e', 'l', 'a']
      return "dec %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0E: # ld reg, byte
      STR = ['c', 'e', 'l', 'a']
      imm = self.fetch()
      return "ld %s, 0x%02X" % (STR[(opcode >> 4) & 3], imm)

    elif opcode == 0x10:
      imm = self.fetch()
      addr = self.PC - 2 + imm - 128
      self.conditional_branch(addr)
      return "djnz %s" % get_label(addr)

    elif opcode == 0x18:
      imm = self.fetch()
      addr = self.PC - 2 + imm - 128
      self.unconditional_jump(addr)
      return "jr %s" % get_label(addr)

    elif opcode == 0x22: # 
      imm = self.fetch()
      imm = imm | (self.fetch() << 8)
      return "ld (0x%04X), hl" % imm

    elif opcode == 0x28:
      imm = self.fetch()
      addr = self.PC - 2 + imm - 128
      self.conditional_branch(addr)
      return "jr z, %s" % get_label(addr)

    elif opcode == 0x32: # 
      imm = self.fetch()
      imm = imm | (self.fetch() << 8)
      return "ld (0x%04X), a" % imm

    elif opcode == 0x3e: # 
      imm = self.fetch()
      return "ld a, 0x%02X" % imm

    elif opcode == 0x3a: # 
      imm = self.fetch()
      imm = imm | (self.fetch() << 8)
      return "ld a, (0x%04X)" % imm

    elif opcode == 0x76:
      self.return_from_subroutine()
      return "halt"

    elif opcode & 0xC0 == 0x40: # ld ??, ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "ld %s, %s" % (STR[(opcode >> 3) & 0x07], STR[opcode & 0x07])

    elif opcode & 0xF8 == 0x80: # add a, ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "add a, %s" % STR[opcode & 0x07]

    elif opcode & 0xF8 == 0x90: # sub ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "sub %s" % STR[opcode & 0x07]

    elif opcode & 0xF8 == 0xA0: # and ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "and %s" % STR[opcode & 0x07]

    elif opcode & 0xF8 == 0xB0: # or ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "or %s" % STR[opcode & 0x07]

    elif opcode & 0xCF == 0xC0: # conditional ret
      STR = ['nz', 'nc', 'po', 'p'] 
      self.return_from_subroutine() # TODO: review this.
      self.schedule_entry_point(self.PC)
      return "ret %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0xC1: # pop reg
      STR = ['bc', 'de', 'hl', 'af']
      return "pop %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0xC5: # push reg
      STR = ['bc', 'de', 'hl', 'af']
      return "push %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0xCA: # jp cond, **
      STR = ['z', 'c', 'pe', 'm']
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.conditional_branch(addr)
      return "jp %s, %s" % (STR[(opcode >> 4) & 3], get_label(addr))

    elif opcode == 0xC3: # jump addr
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.unconditional_jump(addr)
      return "jp %s" % get_label(addr)

    elif opcode == 0xC6:
      value = self.fetch()
      return "add a, 0x%02X" % value

    elif opcode == 0xC9: # RET
      self.return_from_subroutine()
      return "ret"



    elif opcode == 0xCB: # BIT INSTRUCTIONS:
      ext_opcode = self.fetch()

      ext_instructions = {
        0x11: "rl c",
      }
      if ext_opcode in ext_instructions:
        return ext_instructions[ext_opcode]

      elif ext_opcode & 0xC0 == 0x40: # bit n, ??
        STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
        n = (ext_opcode >> 3) & 7
        return "bit %d, %s" % (n, STR[ext_opcode & 0x07])

      else:
        self.illegal_instruction((opcode << 8) | ext_opcode)
        return "; DISASM ERROR! Illegal bit instruction (ext_opcode = 0x%02X)" % ext_opcode


    elif opcode == 0xCC: # conditional CALL
      STR = ['z', 'c', 'pe', 'm']
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.subroutine(addr)
      comment = get_subroutine_comment(addr)
      cond = STR[(opcode >> 4) & 3]
      if comment:
        return "call %s, %s\t; %s" % (cond, get_label(addr), comment)
      else:
        return "call %s, %s" % (cond, get_label(addr))

    elif opcode == 0xcd: # CALL
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.subroutine(addr)
      comment = get_subroutine_comment(addr)
      if comment:
        return "call %s\t; %s" % (get_label(addr), comment)
      else:
        return "call %s" % get_label(addr)

    elif opcode == 0xe6: # 
      imm = self.fetch()
      return "and 0x%02X" % imm

    elif opcode == 0xed: # EXTENDED INSTRUCTIONS:
      ext_opcode = self.fetch()

      ext_instructions = {
        0xb0: "ldir",
      }
      if ext_opcode in ext_instructions:
        return ext_instructions[ext_opcode]
      else:
        self.illegal_instruction((opcode << 8) | ext_opcode)
        return "; DISASM ERROR! Illegal extended instruction (ext_opcode = 0x%02X)" % ext_opcode

    elif opcode == 0xee:
      value = self.fetch()
      return "xor 0x%02X" % value

    elif opcode == 0xf6:
      value = self.fetch()
      return "or 0x%02X" % value

    else:
      self.illegal_instruction(opcode)
      return "; DISASM ERROR! Illegal instruction (opcode = 0x%02X)" % opcode

def makedir(path):
  if not os.path.exists(path):
    os.mkdir(path)

import os
import sys
if len(sys.argv) != 2:
  print("usage: {} <filename.rom>".format(sys.argv[0]))
else:
  gamerom = sys.argv[1]
  makedir(OUTPUT_DIR)
  print "disassembling {}...".format(gamerom)
  trace = MSX_Trace(gamerom, loglevel=0, relocation_address=0x4000)
  trace.run(entry_point=0x4017) #GALAGA!
#  trace.print_ranges()
#  trace.print_grouped_ranges()

  trace.save_disassembly_listing("{}.asm".format(gamerom.split(".")[0]))
