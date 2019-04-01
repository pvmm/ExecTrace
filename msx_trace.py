#!/usr/bin/env python
# (c) 2019 Felipe Correa da Silva Sanches <juca@members.fsf.org>
# Released under the terms of the GNU GPL version 3 or later.
#
# Instruction set described at http://clrhome.org/table/
# MSX BIOS calls documented at http://www.tabalabs.com.br/msx/msx_tech_hb/msxtech_tabalabs.pdf
#
import sys

from exec_trace import ExecTrace, hex8, hex16

def imm16(v):
  if v in KNOWN_SUBROUTINES.keys():
    return KNOWN_SUBROUTINES[v][0]
  else:
    return hex16(v)

KNOWN_VARS = {
  0x4000: ("ROM_HEADER", "label"),
  0x4010: ("ROM_TITLE", "n-str"),
}

KNOWN_SUBROUTINES = {
  0x0047: ("WRTVDP", "Writes to the VDP register."),
  0x004D: ("WRTVRM", "Writes to the VRAM addressed by [HL]."),
  0x005C: ("LIDRVM", "Moves block of memory from memory to VRAM."),
  0x0093: ("WRTPSG", "Writes data to the PSG register."),
  0x0096: ("RDPSG", "Read data from the PSG register."),
  0x0138: ("RSLREG", "Reads the current output to the primary slot register."),
  0x013B: ("WSLREG", "Writes to the primary slot register."),
  0x013E: ("RDVDP", "Reads the VPD status register."),
  0x0141: ("SNSMAT", "Returns the status of a specified row of a keyboard matrix."),
#-------------------------------------
  0x4017: ("ENTRY_POINT", ""),
  0x404A: ("LOOP", "wait for interrupts"),
  0x404C: ("INTERRUPT_HANDLER", ""),
}


jump_tables = []
def register_jump_table(addr):
  if addr not in jump_tables:
    jump_tables.append(addr)

def get_subroutine_comment(addr):
  if addr in KNOWN_SUBROUTINES.keys():
    return KNOWN_SUBROUTINES[addr][1]

def get_label(addr):
  if addr in KNOWN_SUBROUTINES.keys():
    return KNOWN_SUBROUTINES[addr][0]
  elif addr in KNOWN_VARS.keys():
    return KNOWN_VARS[addr][0]
  elif addr < 0x4000:
    sys.exit("Unknown BIOS call: %s" % hex16(addr))
  else:
    return "LABEL_%04X" % addr


def twos_compl(v):
  if v & (1 << 7):
    v -= (1 << 8)
  return v


class MSX_Trace(ExecTrace):
  def output_disasm_headers(self):
    header = "; Generated by MSX_ExecTrace\n"
    header += "; git clone https://git.savannah.nongnu.org/git/z80asm.git\n\n"
#    for var in KNOWN_VARS.keys():
#      name = KNOWN_VARS[var]
#      header += "%s:\tequ %s\n" % (name, hex16(var))

    for addr, v in KNOWN_SUBROUTINES.items():
      if addr < 0x4000:
        label, comment = v
        header += "%s:\tequ %s\t; %s\n" % (label, hex16(addr), comment)

    return header


  def disasm_instruction(self, opcode):

    simple_instructions = {
      0x00: "nop",
      0x07: "rlca",
      0x08: "ex af, af'",
      0x0f: "rrca",
      0x12: "ld (de), a",
      0x17: "rla",
      0x1a: "ld a, (de)",
      0x1f: "rra",
      0x27: "daa",
      0x2f: "cpl",
      0xd9: "exx",
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
      return "ld %s, %s" % (STR[(opcode >> 4) & 3], imm16(imm))

    elif opcode & 0xCF == 0x03: # inc reg16
      STR = ['bc', 'de', 'hl', 'sp']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x04: # inc reg8
      STR = ['b', 'd', 'h', '(hl)']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x05: # dec reg8
      STR = ['b', 'd', 'h', '(hl)']
      return "dec %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x06: # ld _8, byte
      STR = ['b', 'd', 'h', '(hl)']
      imm = self.fetch()
      return "ld %s, %s" % (STR[(opcode >> 4) & 3], hex8(imm))

    elif opcode & 0xCF == 0x09: # add hl, reg16 
      STR = ['bc', 'de', 'hl', 'sp']
      return "add hl, %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0B: #
      STR = ['bc', 'de', 'hl', 'sp']
      return "dec %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0C: # inc reg8
      STR = ['c', 'e', 'l', 'a']
      return "inc %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0D: # dec reg8
      STR = ['c', 'e', 'l', 'a']
      return "dec %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0x0E: # ld reg, byte
      STR = ['c', 'e', 'l', 'a']
      imm = self.fetch()
      return "ld %s, %s" % (STR[(opcode >> 4) & 3], hex8(imm))

    elif opcode == 0x10:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.conditional_branch(addr)
      return "djnz %s" % get_label(addr)

    elif opcode == 0x18:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.unconditional_jump(addr)
      return "jr %s" % get_label(addr)

    elif opcode == 0x20:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.conditional_branch(addr)
      return "jr nz, %s" % get_label(addr)

    elif opcode == 0x22: # 
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      return "ld (%s), hl" % self.getVariableName(addr)

    elif opcode == 0x28:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.conditional_branch(addr)
      return "jr z, %s" % get_label(addr)

    elif opcode == 0x2A:
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      return "ld hl, (%s)" % self.getVariableName(addr)

    elif opcode == 0x30:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.conditional_branch(addr)
      return "jr nc, %s" % get_label(addr)

    elif opcode == 0x32: # 
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      return "ld (%s), a" % self.getVariableName(addr)

    elif opcode == 0x38:
      imm = self.fetch()
      addr = self.PC + twos_compl(imm)
      self.conditional_branch(addr)
      return "jr c, %s" % get_label(addr)

    elif opcode == 0x3e: # 
      imm = self.fetch()
      return "ld a, %s" % hex8(imm)

    elif opcode == 0x3a: # 
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      return "ld a, (%s)" % self.getVariableName(addr)

    elif opcode == 0x76:
      self.return_from_subroutine()
      return "halt"

    elif opcode & 0xC0 == 0x40: # ld ??, ??
      STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "ld %s, %s" % (STR[(opcode >> 3) & 0x07], STR[opcode & 0x07])

    elif opcode & 0xC0 == 0x80:
      STR1 = ['add a,', 'adc a,', 'sub', 'sbc a,', 'and', 'xor', 'or', 'cp']
      STR2 = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
      return "%s %s" % (STR1[(opcode >> 3) & 0x07], STR2[opcode & 0x07])

    elif opcode & 0xC7 == 0xC0: # conditional ret
      STR = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
      self.return_from_subroutine() # TODO: review this.
      self.schedule_entry_point(self.PC)
      return "ret %s" % STR[(opcode >> 3) & 7]

    elif opcode & 0xCF == 0xC1: # pop reg
      STR = ['bc', 'de', 'hl', 'af']
      return "pop %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xC7 == 0xC2: # jp cond, **
      STR = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.conditional_branch(addr)
      return "jp %s, %s" % (STR[(opcode >> 3) & 7], get_label(addr))

    elif opcode & 0xC7 == 0xC4: # conditional CALL
      STR = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.subroutine(addr)
      comment = get_subroutine_comment(addr)
      cond = STR[(opcode >> 3) & 7]
      if comment:
        return "call %s, %s\t; %s" % (cond, get_label(addr), comment)
      else:
        return "call %s, %s" % (cond, get_label(addr))

    elif opcode & 0xCF == 0xC5: # push reg
      STR = ['bc', 'de', 'hl', 'af']
      return "push %s" % STR[(opcode >> 4) & 3]

    elif opcode & 0xCF == 0xC6: # 
      STR = ['add a,', 'sub', 'and', 'or']
      imm = self.fetch()
      return "%s %s" % (STR[(opcode >> 4) & 3], hex8(imm))

    elif opcode & 0xC7 == 0xC7: # rst
      return "rst %s" % hex8(((opcode >> 3) & 7) * 0x08)

    elif opcode == 0xC3: # jump addr
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.unconditional_jump(addr)
      return "jp %s" % get_label(addr)

    elif opcode == 0xC6:
      value = self.fetch()
      return "add a, %s" % hex8(value)

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

      elif ext_opcode & 0xC0 == 0x00: # bit rotates and shifts
        STR1 = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', 'sll', 'srl']
        STR2 = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
        return "%s %s" % (STR1[(ext_opcode >> 3) & 0x07], STR2[ext_opcode & 0x07])

      elif ext_opcode & 0xC0 == 0x40: # bit n, ??
        STR = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
        n = (ext_opcode >> 3) & 7
        return "bit %d, %s" % (n, STR[ext_opcode & 0x07])

      else:
        self.illegal_instruction((opcode << 8) | ext_opcode)
        return "; DISASM ERROR! Illegal bit instruction (ext_opcode = %s)" % hex8(ext_opcode)


    elif opcode == 0xcd: # CALL
      addr = self.fetch()
      addr = addr | (self.fetch() << 8)
      self.subroutine(addr)
      comment = get_subroutine_comment(addr)
      if comment:
        return "call %s\t; %s" % (get_label(addr), comment)
      else:
        return "call %s" % get_label(addr)




    elif opcode in [0xDD, 0xFD]: # IX/IY INSTRUCTIONS:
      i_opcode = self.fetch()
      if opcode == 0xDD:
        ireg = "ix"
      else:
        ireg = "iy"

      i_instructions = {
        0x23: "inc %s",
        0xE1: "pop %s",
        0xE5: "push %s",
      }
      if i_opcode in i_instructions:
        return i_instructions[i_opcode] % ireg

      elif i_opcode == 0x21: #
        imm = self.fetch()
        imm = imm | (self.fetch() << 8)
        return "ld %s, %s" % (ireg, imm16(imm))

      elif i_opcode & 0xCF == 0x4E: #
        STR = ['c', 'e', 'l', 'a']
        imm = self.fetch()
        return "ld %s, (%s + %s)" % (STR[(i_opcode >> 4) & 3], ireg, imm)

      elif i_opcode in [0x46, 0x56, 0x66]: #
        STR = ['b', 'd', 'h']
        imm = self.fetch()
        return "ld %s, (%s + %s)" % (STR[(i_opcode >> 4) & 3], ireg, imm)

      else:
        self.illegal_instruction((opcode << 8) | i_opcode)
        return "; DISASM ERROR! Illegal %s instruction (%s_opcode = %s)" % (ireg, ireg, hex8(i_opcode))



    elif opcode == 0xE6: # 
      imm = self.fetch()
      return "and %s" % hex8(imm)

    elif opcode == 0xE9:
      register_jump_table(self.PC-1)
      return "jp (hl)"

    elif opcode == 0xED: # EXTENDED INSTRUCTIONS:
      ext_opcode = self.fetch()

      ext_instructions = {
        0x44: "neg",
        0x4C: "neg",
        0x52: "sbc hl, de",
        0x54: "neg",
        0x5C: "neg",
        0x64: "neg",
        0x6C: "neg",
        0x74: "neg",
        0x7C: "neg",
        0xb0: "ldir",
      }
      if ext_opcode in ext_instructions:
        return ext_instructions[ext_opcode]

      elif ext_opcode == 0x73:
        addr = self.fetch()
        addr = addr | (self.fetch() << 8)
        return "ld (%s), sp" % self.getVariableName(addr)

      elif ext_opcode == 0x7B:
        addr = self.fetch()
        addr = addr | (self.fetch() << 8)
        return "ld sp, (%s)" % self.getVariableName(addr)

      else:
        self.illegal_instruction((opcode << 8) | ext_opcode)
        return "; DISASM ERROR! Illegal extended instruction (ext_opcode = %s)" % hex8(ext_opcode)

    elif opcode == 0xee:
      value = self.fetch()
      return "xor %s" % hex8(value)

    elif opcode == 0xf6:
      value = self.fetch()
      return "or %s" % hex8(value)

    elif opcode == 0xfe:
      value = self.fetch()
      return "cp %s" % hex8(value)

    else:
      self.illegal_instruction(opcode)
      return "; DISASM ERROR! Illegal instruction (opcode = %s)" % hex8(opcode)

def makedir(path):
  if not os.path.exists(path):
    os.mkdir(path)

import os
import sys
if len(sys.argv) != 2:
  print("usage: {} <filename.rom>".format(sys.argv[0]))
else:
  gamerom = sys.argv[1]
  print "disassembling {}...".format(gamerom)

  # Galaga has got a jump table stored at address 0x95FD (ROM offset 0x55FD)
  # There seem to be 13 entries in that table:
  galaga_jumps = [
    0x9633,
    0x9680,
    0x96b7,
    0x96c3,
    0x96f0,
    0x96d9,
    0x9732,  
    0x9746,  
    0x975e,  
    0x9765,  
    0x9775,  
    0x9784,  
    0x9706,
    0x404C # interrupt handler
  ]
  trace = MSX_Trace(gamerom,
                    loglevel=0,
                    relocation_address=0x4000,
                    jump_table=galaga_jumps,
                    variables=KNOWN_VARS,
                    subroutines=KNOWN_SUBROUTINES)
  trace.run(entry_point=0x4017) #GALAGA!
  #trace.print_grouped_ranges()

  #for codeblock in sorted(trace.visited_ranges, key=lambda cb: cb.start):
  #  print(hex16(codeblock.start), hex16(codeblock.end))

  print('"JP (HL)" instructions found at:\n')
  for t in jump_tables:
    print("\t0x%04X" % t)

  trace.save_disassembly_listing("{}.asm".format(gamerom.split(".")[0]))
