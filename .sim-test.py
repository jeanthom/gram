#!/usr/bin/env python3
import os
import sys
import pexpect
import time
from argparse import ArgumentParser


parser = ArgumentParser()
parser.add_argument("--sdram-module", type=str)
args = parser.parse_args()


tests = [
    {
        'id':      'litex_sim',
        'command': f'python3 -m litex.tools.litex_sim --with-sdram --sdram-module {args.sdram_module}',
        'cwd':     os.getcwd(),
        'checkpoints': [
            { 'timeout': 240, 'good': [b'\n\\s*BIOS built on[^\n]+\n'] },
            { 'timeout': 30,  'good': [b'Memtest OK'],
                              'bad':  [b'(Memory initialization failed|Booting from)'] },
        ]
    }
]


def run_test(id, command, cwd, checkpoints):
    print(f'*** Test ID: {id}')
    print(f'*** CWD:     {cwd}')
    print(f'*** Command: {command}')
    os.chdir(cwd)
    p = pexpect.spawn(command, timeout=None, logfile=sys.stdout.buffer)

    checkpoint_id = 0
    for cp in checkpoints:
        good = cp.get('good', [])
        bad = cp.get('bad', [])
        patterns = good + bad
        timeout = cp.get('timeout', None)

        timediff = time.time()
        try:
            match_id = p.expect(patterns, timeout=timeout)
        except pexpect.EOF:
            print(f'\n*** {id}: premature termination')
            return False;
        except pexpect.TIMEOUT:
            timediff = time.time() - timediff
            print(f'\n*** {id}: timeout (checkpoint {checkpoint_id}: +{int(timediff)}s)')
            return False;
        timediff = time.time() - timediff

        if match_id >= len(good):
            break

        sys.stdout.buffer.write(b'<<checkpoint %d: +%ds>>' % (checkpoint_id, int(timediff)))
        checkpoint_id += 1

    is_success = checkpoint_id == len(checkpoints)

    # Let it print rest of line
    match_id = p.expect_exact([b'\n', pexpect.TIMEOUT, pexpect.EOF], timeout=1)
    p.terminate(force=True)

    line_break = '\n' if match_id != 0 else ''
    print(f'{line_break}*** {id}: {"success" if is_success else "failure"}')

    return is_success


for test in tests:
    success = run_test(**test)
    if not success:
        sys.exit(1)

sys.exit(0)
