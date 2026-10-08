"""Synthetic local voice audition; no user recordings or API keys required."""
import argparse
import csv
import statistics
import time
from pathlib import Path
import httpx

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100:
        parser.error('runs must be 1..100')
    texts = ['Hi. What would you like to work on?',
             'I found the document. Would you like me to save it as a PDF?',
             'Let me check that. Which meeting did you mean, today or tomorrow?']
    output = Path('artifacts')/('voice-'+time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    with httpx.Client(timeout=120, trust_env=False) as client:
        client.get('http://127.0.0.1:8768/health').raise_for_status()
        for i in range(args.runs):
            started = time.perf_counter()
            response = client.post('http://127.0.0.1:8768/tts', json={'text':texts[i%len(texts)]})
            response.raise_for_status()
            elapsed = time.perf_counter()-started
            if response.content[:4] != b'RIFF':
                raise RuntimeError('Invalid WAV response')
            if i < len(texts):
                (output/f'sample-{i+1}.wav').write_bytes(response.content)
            duration = float(response.headers['x-audio-seconds'])
            rows.append({'run':i+1, 'request_seconds':elapsed,
                         'synthesis_seconds':float(response.headers['x-synthesis-seconds']),
                         'audio_seconds':duration, 'real_time_factor':elapsed/max(duration,.001),
                         'peak_allocated_mib':float(response.headers['x-peak-allocated-mib'])})
            print(f'{i+1}: {elapsed:.2f}s for {duration:.2f}s of speech')
    with (output/'results.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print('Median complete-segment latency:',round(statistics.median(r['request_seconds'] for r in rows),3))
    print('Not first-packet or end-to-end conversation latency. Samples/results:',output)

if __name__ == '__main__':
    main()
