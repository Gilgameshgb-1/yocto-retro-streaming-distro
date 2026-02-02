import pexpect
import sys
import time

def pair_controller(mac_address):
    print(f"Bond to controller with MAC: {mac_address}")
    
    # Start bluetoothctl shell
    child = pexpect.spawn('bluetoothctl', timeout=30)
    child.logfile = sys.stdout.buffer #Logger
    
    commands = [
        ('agent NoInputNoOutput', 'Agent registered'),
        ('default-agent', 'Default agent request successful'),
        ('power on', 'Changing power on succeeded'),
        (f'remove {mac_address}', 'Device has been removed'),
        ('scan on', 'Discovery started'),
    ]

    for cmd, expected in commands:
        child.sendline(cmd)
        child.expect(expected)
        time.sleep(1)

    print("\n>>> PUT CONTROLLER IN PAIRING MODE NOW (PS + CREATE) <<<")
    
    child.expect(f'Device {mac_address}', timeout=60)
    
    print("\n>>> DEVICE FOUND. BONDING... <<<")
    child.sendline(f'pair {mac_address}')
    child.expect('Pairing successful', timeout=20)
    
    child.sendline(f'trust {mac_address}')
    child.expect('trust succeeded', timeout=10)
    
    child.sendline(f'connect {mac_address}')
    child.expect('Connection successful', timeout=10)
    
    print("\n--- SUCCESS: CONTROLLER BONDED ---")
    child.sendline('quit')
    child.close()

if __name__ == "__main__":
    MAC = "14:3A:9A:72:C1:B4"
    pair_controller(MAC)