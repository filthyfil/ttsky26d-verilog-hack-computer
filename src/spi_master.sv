// targetting the QSPI PMod where the PSRAM has 8mb,
// the requester must hold we/use_flash/addr/wdata steady from start to done

module spi_master (
	input wire clk,
	input wire rst_n,
	input wire start,
	input wire we,

	input wire use_flash,

	input wire [23:0] addr,
	input wire [15:0] wdata,

	input wire miso,


	output wire busy,
	output wire done,

	output wire [15:0] rdata,

	output wire sck,
	output wire mosi,

	output wire cs0_n,
	output wire cs1_n
);
	wire [47:0] frame = {(we ? 8'h02 : 8'h03), addr, wdata};
	logic [5:0] bit_count;
	logic sck_r;
	logic [15:0] rx;
	logic cs0_n_r;
	logic cs1_n_r;

	typedef enum logic [2:0] {
                IDLE,
        	BUSY,
		DONE
	} spi_master_state;

	spi_master_state state;

	always_ff @(posedge clk) begin
		if (~rst_n) begin // clear
			state <= '0;
			sck_r <= '0;
			cs0_n_r <= 1;
			cs1_n_r <= 1;
			bit_count <= '0;
		end else case (state)
			IDLE: if (start) begin
				cs0_n_r <= ~use_flash;
				cs1_n_r <= use_flash;
				bit_count <= 0;
				state <= BUSY;
			end
			BUSY: if (bit_count == 48) begin
				cs0_n_r <= 1;
				cs1_n_r <= 1;
				state <= DONE;
				end else begin
				sck_man();
			end
			DONE: state <= IDLE;
			default: state <= IDLE;
		endcase
	end

	task automatic sck_man;
		sck_r <= ~sck_r;
		if (sck_r == 0) begin
			if (~we) rx <= {rx[14:0], miso};
		end else begin
			bit_count <= bit_count + 1;
		end
	endtask
	assign rdata = rx;
	assign cs0_n = cs0_n_r;
	assign cs1_n = cs1_n_r;
	assign busy = (state == BUSY);
	assign done = (state == DONE);
	assign mosi = frame[47 - bit_count];
	assign sck = sck_r;
endmodule
