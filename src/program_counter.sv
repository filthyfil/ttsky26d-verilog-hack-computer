module program_counter #(
	parameter WIDTH = 16
)
(
	// i/o
	// input
	input wire clk,
	input wire rst_n,

	input wire [WIDTH-1:0] in,
	input wire load,
	input wire inc,

	// output
	output reg [WIDTH-1:0] out
);
	always @(posedge clk) begin
		if (rst_n == 0) 
			out <= 0;
		else begin
			if (load == 1) 
				out <= in;
			else if (inc == 1)
				out <= out + 1;
			else 
				out <= out;
		end
	end
endmodule
