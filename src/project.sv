/*
 * Copyright (c) 2024 Filip Jasionek
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_filthyfil_hack (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // CPU <-> controller
  wire [15:0] instruction;
  wire [15:0] inM;
  wire [15:0] outM;
  wire        writeM;
  wire [14:0] addressM;
  wire [14:0] pc;
  wire        readM;
  wire        advance;

  // controller <-> spi_master
  wire        mem_req;
  wire        mem_flash;
  wire        mem_we;
  wire [23:0] mem_addr;
  wire [15:0] mem_wdata;
  wire [15:0] mem_rdata;
  wire        mem_done;
  wire        spi_busy;
  wire        spi_start;   

  // I/O
  wire [7:0]  kbd_in;      
  wire [7:0]  io_out;      

  // SPI bus
  wire        sck;         
  wire        mosi;        
  wire        miso;        
  wire        cs0_n;       
  wire        cs1_n;       

  cpu cpu_unit (
      .clk(clk),
      .instruction(instruction),
      .inM(inM),
      .rst_n(rst_n),
      .advance(advance),
      .outM(outM),
      .writeM(writeM),
      .addressM(addressM),
      .pc(pc),
      .readM(readM)
  );

  memory_controller controller (
      .clk(clk),
      .rst_n(rst_n),
      .pc(pc),
      .addressM(addressM),
      .outM(outM),
      .writeM(writeM),
      .readM(readM),
      .instruction(instruction),
      .inM(inM),
      .advance(advance),
      .mem_req(mem_req),
      .mem_flash(mem_flash),
      .mem_we(mem_we),
      .mem_addr(mem_addr),
      .mem_wdata(mem_wdata),
      .mem_rdata(mem_rdata),
      .mem_done(mem_done),
      .kbd_in(kbd_in),
      .io_out(io_out)
  );

  spi_master spi (
      .clk(clk),
      .rst_n(rst_n),
      .start(spi_start),
      .we(mem_we),
      .use_flash(mem_flash),
      .addr(mem_addr),
      .wdata(mem_wdata),
      .miso(miso),
      .busy(spi_busy),
      .done(mem_done),
      .rdata(mem_rdata),
      .sck(sck),
      .mosi(mosi),
      .cs0_n(cs0_n),
      .cs1_n(cs1_n)
  );

  assign spi_start = mem_req & ~spi_busy & ~mem_done;
  assign kbd_in = ui_in;
  assign uo_out = io_out;
  assign uio_out[0] = cs0_n;
  assign uio_out[1] = mosi;
  assign uio_out[2] = '0;
  assign uio_out[3] = sck;
  assign uio_out[5:4] = '0;
  assign uio_out[6] = cs1_n;
  assign uio_out[7] = 1'b1;
  assign miso = uio_in[2];
  assign uio_oe = rst_n ? 8'b1100_1011 : 8'b0;
  

  // List all unused inputs to prevent warnings
  wire _unused = &{ena, uio_in[7:3], uio_in[1:0], 1'b0};

endmodule
