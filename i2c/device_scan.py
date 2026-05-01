from periphery import I2C

def scan_bus(bus_path="/dev/i2c-7"):
    i2c = I2C(bus_path)
    print(f"Scanning {bus_path}...")
    found = []
    for addr in range(0x08, 0x78):
        try:
            i2c.transfer(addr, [I2C.Message([0x00])])
            print(f"  [FOUND] 0x{addr:02X}")
            found.append(addr)
        except:
            pass
    i2c.close()
    if not found:
        print("  No devices found.")
    return found

if __name__ == "__main__":
    scan_bus("/dev/i2c-7")
