## How it works

This project is a 16-bit **Hack** CPU, the computer from *The Elements of Computing Systems* (nand2tetris). It runs standard Hack machine code. A Tiny Tapeout tile is far too small to hold the Hack ROM and RAM, so both live off-chip on a QSPI Pmod: the program runs from SPI flash and the data RAM is SPI PSRAM.

### Blocks

- **CPU** (`cpu.sv`): the standard Hack CPU. It has the A and D registers, a 15-bit program counter, the six-control-bit Hack ALU (`zx nx zy ny f no`, with zero and negative flags), and the jump logic. It decodes A-instructions (`0vvv vvvv vvvv vvvv`) and C-instructions (`111a cccc ccdd djjj`) exactly as the nand2tetris spec describes. Registers and the PC only update on the one cycle per instruction when the memory controller asserts `advance`.
- **Memory controller** (`memory_controller.sv`): runs each instruction through a small state machine:

  ```
  FETCH -> DECIDE -> [READ] -> [WRITE] -> COMMIT -> FETCH ...
  ```

  - **FETCH** reads the instruction at `PC` from flash into an instruction register.
  - **DECIDE** checks whether the instruction reads `M` (the `a` bit is set), writes `M` (the `d3` bit is set), both, or neither.
  - **READ** loads `M` from PSRAM, or from an I/O register, into an M register.
  - **WRITE** stores the ALU result to PSRAM or to an I/O register. If an instruction both reads and writes `M` (for example `M=M+1`), the read happens first, and both use the old value of A.
  - **COMMIT** pulses `advance` so the CPU updates A, D and the PC.
- **SPI master** (`spi_master.sv`): a single-bit SPI mode 0 master. SCK runs at clk/2. Every transfer is one 48-bit frame: an 8-bit command (`0x03` READ or `0x02` WRITE), a 24-bit byte address, then 16 data bits, MSB first. CS0 selects the flash and CS1 selects PSRAM A.

### Memory map

| Hack address      | Device                                         |
|-------------------|------------------------------------------------|
| ROM `0x0000-0x7FFF` | SPI flash (CS0), byte address `2*PC`         |
| RAM `0x6000`      | `KBD`: read-only, returns `ui_in[7:0]` (upper byte 0); writes are ignored |
| RAM `0x6001`      | `OUT`: write sets `uo_out[7:0]` from the low byte; reads return the last value written |
| All other RAM     | SPI PSRAM A (CS1), byte address `2*address`    |

Every word is stored big-endian (high byte first) at byte address `2*word`. Unlike the full Hack platform, there is no memory-mapped screen: `0x4000-0x5FFF` is plain PSRAM. `KBD` keeps its usual Hack address. The only output is the 8-bit `OUT` port.

### Timing

One SPI transfer takes about 100 clocks: 48 bits at 2 clocks per bit, plus overhead. An instruction that doesn't touch `M` costs about 100 clocks (one fetch). Each PSRAM read or write adds about 100 more. Accesses to `KBD` and `OUT` take a single cycle. At 25 MHz the CPU runs at about 125k-250k Hack instructions per second.

### Reset

While `rst_n` is low, all `uio` pins are inputs (`uio_oe = 0`). The design therefore releases the SPI bus during reset, so an external programmer can write the flash. After reset, the PC starts at 0 and the first instruction comes from flash byte address 0.

## How to test

### In simulation

The cocotb testbench in `test/` has an SPI flash/PSRAM model (`spi_mem_model.py`) and runs assembled Hack programs from `test/programs/`:

- `add`: computes `RAM[0] = 2 + 3`.
- `alu_ops`: all 28 comp mnemonics (A and M forms) on two operand pairs.
- `dest_ops`: all 8 destination combinations and a read-modify-write.
- `jump_ops`: all 8 jump conditions on negative, zero and positive values.

```sh
cd test
make -B
```

### On hardware

1. Assemble a Hack program to a `.hack` file with the nand2tetris assembler or any other Hack assembler.
2. Convert it to a binary image with two bytes per instruction, high byte first. For example:

   ```python
   words = [int(l, 2) for l in open("prog.hack").read().split()]
   open("prog.bin", "wb").write(b"".join(w.to_bytes(2, "big") for w in words))
   ```

3. Write `prog.bin` to the Pmod's flash at address 0, for example with the Tiny Tapeout demo board's flash programming tools. Hold `rst_n` low during programming so the design keeps off the SPI bus.
4. Plug in the QSPI Pmod, set the clock (up to 25 MHz), and release reset. The program starts running at once.
5. Use the 8 input switches (`ui_in`) as the `KBD` word, read at RAM `0x6000`. Watch `OUT` (RAM `0x6001`) on the 8 output pins (`uo_out`), for example on the LEDs or the 7-segment display.

A minimal program that copies the switches to the outputs:

```
(LOOP)
@24576   // KBD
D=M
@24577   // OUT
M=D
@LOOP
0;JMP
```

## External hardware

- **QSPI Pmod** (SPI flash and PSRAM, e.g. the Tiny Tapeout QSPI Pmod) on the bidirectional `uio` header:
  - `uio[0]`: CS0, flash (program ROM)
  - `uio[1]`: MOSI
  - `uio[2]`: MISO
  - `uio[3]`: SCK
  - `uio[6]`: CS1, PSRAM A (data RAM)
  - `uio[7]`: CS2, PSRAM B (unused, held high)

  The flash and PSRAM must both support the plain single-bit `0x03` READ command with no dummy cycles. The PSRAM must also support `0x02` WRITE. The flash is only ever read.
- **Input switches** on `ui_in[7:0]` (keyboard/input word).
- **LEDs or a 7-segment display** on `uo_out[7:0]` (output port).
