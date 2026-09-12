"""Reproduce the preliminary local sweep in a fresh output directory.

Usage: .venv/Scripts/python.exe PATH/measure_local.py [NEW_OUTPUT_DIRECTORY]
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pyperf


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUTPUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE
OUTPUT.mkdir(parents=True, exist_ok=True)
BASELINE = HERE / 'baseline.py'
SOURCE = ROOT / 'suites/optimized/bm_raytrace/run_benchmark.py'
VARIANTS = [('scalar', BASELINE, [])] + [
    (f'batch-{size}', SOURCE, [f'--batch-size={size}'])
    for size in (1, 2, 10, 100, 256, 512, 1024)]
ORDERS = [list(range(8)), list(reversed(range(8))), [3, 4, 5, 6, 7, 0, 1, 2]]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, data):
    with (OUTPUT / name).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def main():
    write_json('measurement_metadata.json', {
        'python': sys.version, 'baseline_sha256': sha(BASELINE),
        'optimized_sha256': sha(SOURCE),
        'original_sha256': sha(ROOT / 'suites/original/bm_raytrace/run_benchmark.py'),
        'orders': [[VARIANTS[i][0] for i in order] for order in ORDERS],
        'note': 'Windows local measurements, not server results. One logical CPU.',
    })
    for round_number, order in enumerate(ORDERS, 1):
        for index in order:
            name, source, options = VARIANTS[index]
            path = OUTPUT / f'round-{round_number:02d}-{name}.json'
            cmd = [sys.executable, str(source), '--width=100', '--height=100',
                   '--affinity=0', '--processes=1', '--values=3', '--warmups=1',
                   '--loops=1', '-o', str(path), *options]
            print(f'Round {round_number}: {name}', flush=True)
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            with (OUTPUT / 'benchmark_log.txt').open('a', encoding='utf-8') as log:
                log.write(json.dumps(cmd) + '\n' + result.stdout + result.stderr + '\n')
            result.check_returncode()
            bench = pyperf.BenchmarkSuite.load(str(path)).get_benchmark('raytrace')
            print(f'  {bench.mean() * 1000:.3f} ms', flush=True)
    rows = []
    for name, source, options in VARIANTS:
        combined = None
        round_means = []
        for number in range(1, len(ORDERS) + 1):
            bench = pyperf.BenchmarkSuite.load(
                str(OUTPUT / f'round-{number:02d}-{name}.json')).get_benchmark('raytrace')
            round_means.append(bench.mean() * 1000)
            if combined is None:
                combined = bench
            else:
                combined.add_runs(bench)
        combined.dump(str(OUTPUT / f'{name}.json'))
        rows.append({'variant': name, 'mean_ms': combined.mean() * 1000,
                     'stdev_ms': combined.stdev() * 1000,
                     'round_means_ms': round_means, 'values': len(combined.get_values())})
    for row in rows:
        row['speedup_vs_scalar'] = rows[0]['mean_ms'] / row['mean_ms']
    write_json('timing_summary.json', rows)
    print(json.dumps(rows, indent=2), flush=True)


if __name__ == '__main__':
    main()
