"""Build the narrated video of one recorded run.

Input: a driver run directory made with --record-tui (tui.cast, operator.jsonl, events.jsonl)
and a narration file. Each narration segment names the part of the recording it talks over;
that part is replayed at whatever constant speed makes it last as long as the spoken text,
so the picture is always the real terminal, only faster. Output: 1920x1080, 30 fps, H.264 +
AAC, subtitles burned in and also muxed as a text track, plus a .srt file.
"""

import argparse
import json
from pathlib import Path
import subprocess
import sys
import textwrap

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import termrender  # noqa: E402
import tts  # noqa: E402

W, H, FPS = 1920, 1080, 30
INTER = '/usr/share/fonts/opentype/inter/'
BG = (9, 11, 18)


def font(name: str, size: int):
    return ImageFont.truetype(INTER + name, size)


def anchors(run: Path) -> dict:
    """Named moments of the run, in seconds from the start of the terminal recording."""
    header = json.loads((run / 'tui.cast').open().readline())
    start = float((run / 'tui-started.txt').read_text()) if (run / 'tui-started.txt').exists() else header['timestamp']
    operator = [json.loads(line) for line in (run / 'operator.jsonl').read_text().split('\n') if line]
    events = [json.loads(line) for line in (run / 'events.jsonl').read_text().split('\n') if line.strip()]
    session = (run / 'session-id.txt').read_text().strip()
    at = {'start': 0.0}
    gates = [e for e in operator if e['kind'] == 'gate']
    for index, gate in enumerate(gates, 1):
        at[f'gate{index}_seen'] = gate['seen'] - start
        at[f'gate{index}_replied'] = gate['replied'] - start
    turns = [e for e in operator if e['kind'] == 'agent-turn-ended']
    for index, turn in enumerate(turns, 1):
        at[f'turn{index}_end'] = turn['at'] - start
    replies = [e for e in operator if e['kind'] == 'chat-reply']
    for index, reply in enumerate(replies, 1):
        at[f'reply{index}'] = reply['at'] - start
    created = [e['created'] / 1000 - start for e in events if e['type'] == 'session.created'
               and (e.get('data') or {}).get('sessionID') != session]
    done = [e['created'] / 1000 - start for e in events if e['type'] == 'session.execution.succeeded'
            and (e.get('data') or {}).get('sessionID') != session]
    if created:
        at['reviewers_start'], at['reviewers_done'] = min(created), max(done or created)
    at['end'] = next(e['at'] for e in operator if e['kind'] == 'finished') - start
    return at


def resolve(expression: str, at: dict) -> float:
    """'gate1_seen', 'gate1_seen+4', 'reviewers_start-2' or a number."""
    for sign in '+-':
        if sign in expression[1:]:
            name, offset = expression.rsplit(sign, 1)
            return resolve(name, at) + float(sign + offset)
    return float(at[expression]) if expression in at else float(expression)


def card(title: str, lines: list, footer: str = '') -> Image.Image:
    image = Image.new('RGB', (W, H), BG)
    draw = ImageDraw.Draw(image)
    y = 140
    for wrapped in textwrap.wrap(title, 44):
        draw.text((164, y), wrapped, font=font('Inter-Bold.otf', 66), fill=(240, 242, 250))
        y += 84
    draw.rectangle([120, 150, 132, y - 10], fill=(27, 110, 243))
    y += 50
    for line in lines:
        colour = (214, 217, 230)
        if line.startswith('+ '):
            colour, line = (158, 206, 106), '✓  ' + line[2:]
        elif line.startswith('- '):
            colour, line = (247, 118, 142), '✗  ' + line[2:]
        elif line.startswith('? '):
            colour, line = (224, 175, 104), '?  ' + line[2:]
        marked = line[:1] in '✓✗?'
        for number, wrapped in enumerate(textwrap.wrap(line, 76) or ['']):
            draw.text((164, y), ('   ' if marked and number else '') + wrapped,
                      font=ImageFont.truetype(termrender.FONT_DIR + 'JetBrainsMono-Regular.ttf', 34)
                      if marked else font('Inter-Regular.otf', 38), fill=colour)
            y += 56
        y += 10
    if footer:
        draw.text((164, H - 250), footer, font=font('Inter-Regular.otf', 28), fill=(122, 130, 160))
    return image


def compose(body: Image.Image, caption: str, badge: str, label: str) -> Image.Image:
    """Place a terminal frame or card on the canvas and draw the subtitle band."""
    if body.size == (W, H):
        frame = body.copy()
    else:
        frame = Image.new('RGB', (W, H), BG)
        left, top = (W - body.width) // 2, 28
        draw = ImageDraw.Draw(frame)
        draw.rounded_rectangle([left - 14, top - 14, left + body.width + 13, top + body.height + 13],
                               radius=14, fill=(13, 15, 23), outline=(40, 44, 62), width=2)
        frame.paste(body, (left, top))
    draw = ImageDraw.Draw(frame)
    if label:
        draw.text((96, H - 44), label, font=font('Inter-Regular.otf', 22), fill=(96, 104, 134))
    if badge:
        box = draw.textbbox((0, 0), badge, font=font('Inter-SemiBold.otf', 26))
        x = W - 96 - (box[2] - box[0])
        draw.rounded_rectangle([x - 16, H - 52, W - 80, H - 12], radius=10, fill=(27, 40, 72))
        draw.text((x, H - 48), badge, font=font('Inter-SemiBold.otf', 26), fill=(125, 166, 255))
    if caption:
        lines = textwrap.wrap(caption, 78)[:2]
        y = H - 138 if len(lines) == 2 else H - 116
        if body.size == (W, H):
            draw.rectangle([0, H - 160, W, H - 60], fill=BG)
        for line in lines:
            width = draw.textlength(line, font=font('Inter-Medium.otf', 36))
            draw.text(((W - width) / 2, y), line, font=font('Inter-Medium.otf', 36), fill=(245, 246, 252))
            y += 46
    return frame


def caption_chunks(text: str, duration: float):
    """Split narration into subtitle cues (one sentence or clause each) timed by share of characters."""
    import re
    chunks = []
    for sentence in re.split(r'(?<=[.?!])\s+', text.strip()):
        sentence = sentence.strip()
        while len(sentence) > 96:  # two caption lines at most
            cut = max(sentence.rfind(', ', 0, 96), sentence.rfind(' and ', 0, 96))
            cut = cut + 1 if cut > 30 else sentence.rfind(' ', 0, 96)
            chunks.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            chunks.append(sentence)
    total, clock, cues = sum(len(c) for c in chunks), 0.0, []
    for chunk in chunks:
        span = duration * len(chunk) / total
        cues.append((clock, clock + span, chunk))
        clock += span
    return cues


def stamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    return f'{millis // 3600000:02d}:{millis // 60000 % 60:02d}:{millis // 1000 % 60:02d},{millis % 1000:03d}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--narration', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--work', required=True, help='directory for intermediate audio')
    parser.add_argument('--preview', help='write one PNG per segment here instead of the video')
    args = parser.parse_args()
    run, work = Path(args.run), Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    script = json.loads(Path(args.narration).read_text())
    at = anchors(run)
    print('anchors', json.dumps({k: round(v, 1) for k, v in at.items()}))
    columns, rows, cast = termrender.load(str(run / 'tui.cast'))

    voice = tts.Kokoro()
    segments, clock, audio_parts, cues = [], 0.0, [], []
    for index, segment in enumerate(script['segments']):
        sentences = [s for s in segment['say'].split('|') if s.strip()]
        def pronounce(text: str) -> str:
            # Subtitles keep the written form; the voice gets a speakable one.
            for written, said in script.get('pronounce', {}).items():
                text = text.replace(written, said)
            return text
        spoken = [voice.speak(pronounce(s.strip()), speed=script.get('speed', 1.0)) for s in sentences]
        gap = np.zeros(int(0.28 * tts.RATE), dtype=np.float32)
        sound = np.concatenate([part for s in spoken for part in (s, gap)])
        pad = segment.get('pad', 0.45)
        duration = len(sound) / tts.RATE + pad
        duration = round(duration * FPS) / FPS
        sound = np.concatenate([sound, np.zeros(int(duration * tts.RATE) - len(sound), dtype=np.float32)])
        audio_parts.append(sound)
        offset = 0.0
        for sentence, part in zip(sentences, spoken):
            length = len(part) / tts.RATE
            for a, b, chunk in caption_chunks(sentence.strip(), length):
                cues.append((clock + offset + a, clock + offset + b + 0.12, chunk))
            offset += length + 0.28
        entry = {'start': clock, 'duration': duration, **segment}
        if 'from' in segment:
            entry['a'], entry['b'] = resolve(segment['from'], at), resolve(segment['to'], at)
            entry['rate'] = (entry['b'] - entry['a']) / duration
        segments.append(entry)
        print(f"segment {index}: {duration:5.1f}s  " + (f"source {entry['a']:.0f}-{entry['b']:.0f}s x{entry['rate']:.1f}" if 'a' in entry else 'card'))
        clock += duration
    total = clock
    print(f'total {total:.1f}s')
    tts.write_wav(str(work / 'narration.wav'), np.concatenate(audio_parts))
    # A cue never runs into the next one.
    cues = [(a, min(b, cues[i + 1][0]) if i + 1 < len(cues) else b, text) for i, (a, b, text) in enumerate(cues)]
    srt = Path(args.output).with_suffix('.srt')
    srt.write_text(''.join(f'{i}\n{stamp(a)} --> {stamp(min(b, total))}\n{text}\n\n'
                           for i, (a, b, text) in enumerate(cues, 1)))

    terminal = termrender.Terminal(columns, rows)
    position = 0  # next cast event to feed

    def terminal_at(source_time: float) -> Image.Image:
        nonlocal position, cached, cached_version
        while position < len(cast) and cast[position][0] <= source_time:
            terminal.feed(cast[position][1])
            position += 1
        if cached_version != terminal.version:
            cached, cached_version = terminal.image(), terminal.version
        return cached

    cached, cached_version = None, -1
    cards = {}
    encoder = None
    if not args.preview:
        encoder = subprocess.Popen([
            'ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
            '-r', str(FPS), '-i', '-', '-i', str(work / 'narration.wav'), '-i', str(srt),
            '-map', '0:v', '-map', '1:a', '-map', '2:s', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
            '-pix_fmt', 'yuv420p', '-r', str(FPS), '-af', 'volume=-2dB', '-c:a', 'aac', '-b:a', '128k', '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=eng', '-movflags', '+faststart', '-t', f'{total:.3f}', args.output],
            stdin=subprocess.PIPE)
    last_key, last_bytes, previous_body = None, None, None
    frames = round(total * FPS)
    for number in range(frames):
        now = number / FPS
        index = max(i for i, s in enumerate(segments) if s['start'] <= now + 1e-9)
        segment = segments[index]
        local = now - segment['start']
        if 'a' in segment:
            body = terminal_at(segment['a'] + local * segment['rate'])
            rate = segment['rate']
            badge = f'▶▶ ×{rate:.0f}' if rate >= 1.5 else 'real time'
            key = ('t', cached_version)
        else:
            if index not in cards:
                cards[index] = card(segment['title'], segment['lines'], segment.get('footer', ''))
            body, badge, key = cards[index], '', ('c', index)
        caption = next((text for a, b, text in cues if a <= now < b), '')
        # Short cross-fade when the picture changes from a card to the terminal or back.
        fade = min(1.0, local / 0.4) if index and ('a' in segment) != ('a' in segments[index - 1]) else 1.0
        key = (*key, caption, badge, round(fade, 2))
        if key != last_key:
            frame = compose(body, caption, badge, script.get('label', ''))
            if fade < 1.0 and previous_body is not None:
                frame = Image.blend(compose(previous_body, caption, '', script.get('label', '')), frame, fade)
            last_key, last_bytes = key, frame.tobytes()
            if args.preview and local < 1 / FPS + 1e-9:
                pass
        if fade >= 1.0:
            previous_body = body
        if args.preview:
            if abs(local - segment['duration'] * 0.6) < 0.5 / FPS:
                Path(args.preview).mkdir(parents=True, exist_ok=True)
                Image.frombytes('RGB', (W, H), last_bytes).save(Path(args.preview) / f'segment-{index}.png')
        else:
            encoder.stdin.write(last_bytes)
        if number % 300 == 0:
            print(f'frame {number}/{frames}', flush=True)
    if encoder:
        encoder.stdin.close()
        sys.exit(encoder.wait())


if __name__ == '__main__':
    main()
