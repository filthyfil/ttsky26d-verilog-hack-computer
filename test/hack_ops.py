"""
Spec for the instruction-coverage tests: one place that defines what each
test program does AND what it should leave in RAM.

    python3 hack_ops.py        # regenerate programs/*_ops.asm
    ~/hack/assembler/Assembler programs/<name>.asm   # -> programs/<name>.hack

test.py imports this module for the expected values. Expected results come
from the Hack *semantics* of each mnemonic (D+A, D&M, ...), not from the
encoding table, so a wrong bit in the assembler table or in the RTL decoder
both show up as failures.

Every program ends by writing DONE_VALUE to DONE_ADDR, then spins in a halt
loop; the test polls for that marker, so it never depends on PC visibility
(which matters for the gate-level sim).
"""

from pathlib import Path

MASK = 0xFFFF
DONE_ADDR = 4000
DONE_VALUE = 0x600D


def u16(x):
    return x & MASK


# ---------------------------------------------------------------- comp
# all 28 Hack comp mnemonics: f(d, a_or_m) -> result
COMPS = {
    "0":   lambda d, y: 0,
    "1":   lambda d, y: 1,
    "-1":  lambda d, y: u16(-1),
    "D":   lambda d, y: d,
    "A":   lambda d, y: y,
    "!D":  lambda d, y: u16(~d),
    "!A":  lambda d, y: u16(~y),
    "-D":  lambda d, y: u16(-d),
    "-A":  lambda d, y: u16(-y),
    "D+1": lambda d, y: u16(d + 1),
    "A+1": lambda d, y: u16(y + 1),
    "D-1": lambda d, y: u16(d - 1),
    "A-1": lambda d, y: u16(y - 1),
    "D+A": lambda d, y: u16(d + y),
    "D-A": lambda d, y: u16(d - y),
    "A-D": lambda d, y: u16(y - d),
    "D&A": lambda d, y: d & y,
    "D|A": lambda d, y: d | y,
}
# the a=1 forms: same function, y comes from M instead of A
COMPS.update({k.replace("A", "M"): f for k, f in list(COMPS.items()) if "A" in k})
assert len(COMPS) == 28

# operand pairs (D, A/M). A-instructions are 15-bit, so both must be <= 0x7FFF.
#   pair 0: generic bit patterns, D-A goes negative
#   pair 1: D+A carries into the sign bit, A-D goes negative
ALU_PAIRS = [(0x1234, 0x5678), (0x7FF0, 0x001F)]
ALU_Y_ADDR = 900          # RAM[900 + p] holds pair p's y, for the M forms
ALU_RESULT_BASE = 1000    # RAM[1000 + 32*p + i] = result of comp i on pair p


def alu_result_addr(p, i):
    return ALU_RESULT_BASE + 32 * p + i


def alu_program():
    asm = ["// every comp mnemonic on each operand pair; D=<comp>, result -> RAM"]
    for p, (x, y) in enumerate(ALU_PAIRS):
        asm += [f"// pair {p}: D={x:#06x} y={y:#06x}",
                f"@{y}", "D=A", f"@{ALU_Y_ADDR + p}", "M=D"]
        for i, comp in enumerate(COMPS):
            y_src = f"@{ALU_Y_ADDR + p}" if "M" in comp else f"@{y}"
            asm += [f"// {comp}", f"@{x}", "D=A", y_src, f"D={comp}",
                    f"@{alu_result_addr(p, i)}", "M=D"]
    return asm


def alu_expected():
    exp = {}
    for p, (x, y) in enumerate(ALU_PAIRS):
        exp[ALU_Y_ADDR + p] = y
        for i, (comp, f) in enumerate(COMPS.items()):
            exp[alu_result_addr(p, i)] = f(x, y)
    return exp


# ---------------------------------------------------------------- dest
# every dest combination on `@T  <dest>=A+1` (result T+1), with D preset to a
# sentinel. Each case runs twice: once saving D afterwards, once saving A
# (saving one clobbers the other). M must land at the OLD A (= T), never T+1.
DESTS = ["", "M", "D", "MD", "A", "AM", "AD", "AMD"]
DEST_SENTINEL = 1111
DEST_BASE = 2000   # per case k: T_D = 2000+8k, T_A = 2000+8k+4  (T+1 kept free)
DEST_OBS = 2200    # RAM[2200 + 2k] = D after, RAM[2200 + 2k + 1] = A after

# read-modify-write in one instruction: READ then WRITE to the same (old) A.
# AM=M-1 is how compiled VM code pops the stack, so it matters.
RMW_ADDR = 2400
RMW_INIT = 0x0123
RMW_CASES = ["M=M+1", "AM=M-1", "MD=M+1"]   # case r uses RAM[2400 + 4r]
RMW_OBS = 2500     # RAM[2500 + 2r] = D after, RAM[2500 + 2r + 1] = A after


def _dest_case(dest, t, obs_reg, obs_addr):
    instr = f"{dest}=A+1" if dest else "A+1"
    save = ["@" + str(obs_addr), "M=D"] if obs_reg == "D" else \
           ["D=A", "@" + str(obs_addr), "M=D"]
    return [f"// {instr} @ {t}, save {obs_reg}",
            f"@{DEST_SENTINEL}", "D=A", f"@{t}", instr] + save


def _rmw_case(instr, t, obs_reg, obs_addr):
    save = ["@" + str(obs_addr), "M=D"] if obs_reg == "D" else \
           ["D=A", "@" + str(obs_addr), "M=D"]
    return [f"// {instr} @ {t}, save {obs_reg}",
            f"@{RMW_INIT}", "D=A", f"@{t}", "M=D",          # RAM[t] = init
            f"@{DEST_SENTINEL}", "D=A", f"@{t}", instr] + save


def dest_program():
    asm = ["// every dest combination, plus read-modify-write"]
    for k, dest in enumerate(DESTS):
        asm += _dest_case(dest, DEST_BASE + 8 * k, "D", DEST_OBS + 2 * k)
        asm += _dest_case(dest, DEST_BASE + 8 * k + 4, "A", DEST_OBS + 2 * k + 1)
    for r, instr in enumerate(RMW_CASES):
        asm += _rmw_case(instr, RMW_ADDR + 4 * r, "D", RMW_OBS + 2 * r)
        asm += _rmw_case(instr, RMW_ADDR + 4 * r + 2, "A", RMW_OBS + 2 * r + 1)
    return asm


def dest_expected():
    """Returns {addr: value}; value None means 'must never be written'."""
    exp = {}
    for k, dest in enumerate(DESTS):
        for t, obs_addr, reg in ((DEST_BASE + 8 * k, DEST_OBS + 2 * k, "D"),
                                 (DEST_BASE + 8 * k + 4, DEST_OBS + 2 * k + 1, "A")):
            res = t + 1
            exp[t] = res if "M" in dest else None
            exp[t + 1] = None                       # M must not use the new A
            exp[obs_addr] = (res if "D" in dest else DEST_SENTINEL) if reg == "D" \
                else (res if "A" in dest else t)
    for r, instr in enumerate(RMW_CASES):
        dest, comp = instr.split("=")
        res = COMPS[comp](0, RMW_INIT)
        for t, obs_addr, reg in ((RMW_ADDR + 4 * r, RMW_OBS + 2 * r, "D"),
                                 (RMW_ADDR + 4 * r + 2, RMW_OBS + 2 * r + 1, "A")):
            exp[t] = res
            exp[obs_addr] = (res if "D" in dest else DEST_SENTINEL) if reg == "D" \
                else (res if "A" in dest else t)
    return exp


# ---------------------------------------------------------------- jump
# every jump condition against a negative, zero and positive ALU output.
JUMPS = {
    "":    lambda v: False,
    "JGT": lambda v: v > 0,
    "JEQ": lambda v: v == 0,
    "JGE": lambda v: v >= 0,
    "JLT": lambda v: v < 0,
    "JNE": lambda v: v != 0,
    "JLE": lambda v: v <= 0,
    "JMP": lambda v: True,
}
JUMP_VALUES = {"-1": -1, "0": 0, "1": 1}   # D=<comp> sets the value tested
JUMP_RESULT_BASE = 3000   # RAM[3000 + 3j + v] = 1 if taken, 0 if not


def jump_program():
    asm = ["// every jump condition on D<0, D=0, D>0; 1=taken, 0=not taken"]
    for j, jmp in enumerate(JUMPS):
        for v, comp in enumerate(JUMP_VALUES):
            n = f"{j}_{v}"
            res = JUMP_RESULT_BASE + 3 * j + v
            asm += [f"// D={comp}; D;{jmp or '(none)'}",
                    f"D={comp}", f"@TAKEN_{n}", f"D;{jmp}" if jmp else "D",
                    f"@{res}", "M=0", f"@NEXT_{n}", "0;JMP",
                    f"(TAKEN_{n})", f"@{res}", "M=1",
                    f"(NEXT_{n})"]
    return asm


def jump_expected():
    return {JUMP_RESULT_BASE + 3 * j + v: int(f(val))
            for j, f in enumerate(JUMPS.values())
            for v, val in enumerate(JUMP_VALUES.values())}


# ---------------------------------------------------------------- output
PROGRAMS = {
    "alu_ops": (alu_program, alu_expected),
    "dest_ops": (dest_program, dest_expected),
    "jump_ops": (jump_program, jump_expected),
}

EPILOGUE = [f"// done marker, then halt",
            f"@{DONE_VALUE}", "D=A", f"@{DONE_ADDR}", "M=D",
            "(END)", "@END", "0;JMP"]


def write_programs(out_dir=Path(__file__).parent / "programs"):
    for name, (prog, _) in PROGRAMS.items():
        text = "// generated by test/hack_ops.py, do not edit\n"
        text += "\n".join(prog() + EPILOGUE) + "\n"
        (out_dir / f"{name}.asm").write_text(text)
        print(f"wrote {out_dir / name}.asm")


if __name__ == "__main__":
    write_programs()
