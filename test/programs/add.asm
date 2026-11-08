// Computes RAM[0] = 2 + 3
@2
D=A
@3
D=D+A
@0
M=D
// halt: spin here forever so the PC never runs off the end of the program
(END)
@END
0;JMP
