# author fj

from cocotb.triggers import RisingEdge

async def spi_mem(dut, rom: dict, ram: dict):
    while True:
        while True:
            """ 
                wait for when CS0 or CS1 goes low;
                here:
                dut.uio_out[0] := cs0_n := flash (instruction ROM)
                dut.uio_out[6] := cs1_n := PSRAM (data RAM)
            """
            await RisingEdge(dut.clk)
            # read single pins, not the whole bus: an X on a pin we don't
            # care about (e.g. MOSI during a read's data phase) must not crash us
            cs0_n = int(dut.uio_out.value[0])
            cs1_n = int(dut.uio_out.value[6])
            if (cs0_n == 0 or cs1_n == 0):
                break
        """
            one CS has gone low; so start memory transaction
        """
        mem_device = rom if (cs0_n == 0) else ram
        bits = 0
        count = 0 
        prev_sck = 0
        while count < 32:
            await RisingEdge(dut.clk)
            sck = int(dut.uio_out.value[3])
            if (prev_sck == 0 and sck == 1):
                mosi = int(dut.uio_out.value[1])   # only sample MOSI when we use it
                bits = (bits << 1) | mosi
                count += 1
            prev_sck = sck
        cmd = bits >> 24
        addr = bits & 0xFFFFFF
        print("cs0_n", cs0_n, "cmd", hex(cmd), "addr", hex(addr))
        """ handle read or write to memory device """
        word = addr >> 1
        """ handle READ """
        if (cmd == 0x03):
            count = 0
            w = mem_device.get(word, 0)
            dut.uio_in.value = ((w >> 15) & 1) << 2
            count += 1
            while count < 16:
                await RisingEdge(dut.clk)
                sck = int(dut.uio_out.value[3])
                if (prev_sck == 0 and sck == 1):
                    bit = (w >> (15 - count) & 1) 
                    dut.uio_in.value = bit << 2
                    count += 1
                prev_sck = sck
        """ handle WRITE """
        if (cmd == 0x02): 
            count = 0
            while count < 16:
                await RisingEdge(dut.clk)
                sck = int(dut.uio_out.value[3])
                if (prev_sck == 0 and sck == 1):
                    mosi = int(dut.uio_out.value[1])
                    bits = (bits << 1) | mosi
                    count += 1
                prev_sck = sck
            wdata = bits & 0xFFFF   # bits holds [cmd | addr | data]; data is the low 16
            mem_device[word] = wdata
        while (cs0_n == 0 or cs1_n == 0):
            """ wait until csX is released """
            await RisingEdge(dut.clk)
            cs0_n = int(dut.uio_out.value[0])
            cs1_n = int(dut.uio_out.value[6])
