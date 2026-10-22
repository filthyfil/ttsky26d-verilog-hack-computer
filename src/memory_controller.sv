// runs one Hack instruction at a time over SPI:
// FETCH (flash) -> DECIDE -> [READ (PSRAM/IO)] -> [WRITE (PSRAM/IO)] -> COMMIT
// see memory_controller_spec.md
module memory_controller (
	input  wire        clk,
	input  wire        rst_n,

	// CPU side
	input  wire [14:0] pc,
	input  wire [14:0] addressM,
	input  wire [15:0] outM,
	input  wire        writeM,
	input  wire        readM,
	output wire [15:0] instruction,   // from the instruction register (IR)
	output wire [15:0] inM,           // from the M register
	output wire        advance,       // 1 for exactly one clk per instruction

	// memory request port, to spi_master
	output wire        mem_req,       // held high until mem_done
	output wire        mem_flash,     // 1: flash (CS0, fetch), 0: PSRAM (CS1, data)
	output wire        mem_we,
	output wire [23:0] mem_addr,      // byte address
	output wire [15:0] mem_wdata,
	input  wire [15:0] mem_rdata,
	input  wire        mem_done,      // 1-clk pulse; rdata valid for reads

	// I/O
	input  wire [7:0]  kbd_in,        // ui_in
	output wire [7:0]  io_out         // uo_out
);
	localparam [14:0] KBD_ADDR = 15'h6000;
	localparam [14:0] OUT_ADDR = 15'h6001;

	typedef enum logic [2:0] {
		FETCH,
		DECIDE,
		READ,
		AFTER_READ,
		WRITE,
		COMMIT
	} memory_controller_state;
	memory_controller_state m_c_state, m_c_n_state;

	logic [15:0] ir;       // instruction register
	logic [15:0] m_reg;    // M value for the CPU
	logic [7:0]  io_out_r;

	wire is_kbd = (addressM == KBD_ADDR);
	wire is_out = (addressM == OUT_ADDR);
	wire is_io  = is_kbd | is_out;

	// next state
	always_comb begin
		m_c_n_state = m_c_state;
		case (m_c_state)
			FETCH: if (mem_done) m_c_n_state = DECIDE;
			DECIDE: begin // read before write
				if (readM)       m_c_n_state = READ;
				else if (writeM) m_c_n_state = WRITE;
				else             m_c_n_state = COMMIT;
			end
			READ: if (is_io | mem_done) m_c_n_state = AFTER_READ;
			AFTER_READ: begin
				if (writeM) m_c_n_state = WRITE;
				else        m_c_n_state = COMMIT;
			end
			WRITE: if (is_io | mem_done) m_c_n_state = COMMIT;
			COMMIT: m_c_n_state = FETCH;
			default: m_c_n_state = FETCH;
		endcase
	end

	always_ff @(posedge clk) begin
		if (~rst_n) begin
			m_c_state <= FETCH;
			io_out_r <= '0;
		end else begin
			m_c_state <= m_c_n_state;
			case (m_c_state)
				FETCH: if (mem_done) ir <= mem_rdata;
				READ: begin
					if (is_kbd)        m_reg <= {8'b0, kbd_in};
					else if (is_out)   m_reg <= {8'b0, io_out_r};
					else if (mem_done) m_reg <= mem_rdata;
				end
				WRITE: if (is_out) io_out_r <= outM[7:0]; // KBD writes are ignored
				default: ;
			endcase
		end
	end

	// memory requests: driven from the state and pc/addressM/outM, which only
	// change on advance, so they stay steady while mem_req is high
	assign mem_req   = rst_n & ((m_c_state == FETCH) |
	                            (((m_c_state == READ) | (m_c_state == WRITE)) & ~is_io));
	assign mem_flash = (m_c_state == FETCH);
	assign mem_we    = (m_c_state == WRITE);
	assign mem_addr  = mem_flash ? {8'b0, pc, 1'b0}              // ROM from 0x000000
	                             : {7'b0, 1'b1, addressM, 1'b0}; // RAM from 0x010000
	assign mem_wdata = outM;

	assign advance     = (m_c_state == COMMIT);
	assign instruction = ir;
	assign inM         = m_reg;
	assign io_out      = io_out_r;
endmodule
