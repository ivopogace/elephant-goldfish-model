"""Kokoro-82M (ONNX) text to speech with the af_heart voice, using espeak-ng for phonemes."""

import json
from pathlib import Path
import re
import subprocess
import wave

import numpy as np
import onnxruntime as ort

RATE = 24000


class Kokoro:
    def __init__(self, root: str = '/opt/kokoro', voice: str = 'af_heart'):
        root = Path(root)
        self.vocab = json.loads((root / 'tokenizer.json').read_text())['model']['vocab']
        self.session = ort.InferenceSession(str(root / 'model.onnx'), providers=['CPUExecutionProvider'])
        self.styles = np.fromfile(root / f'{voice}.bin', dtype=np.float32).reshape(-1, 1, 256)

    def phonemes(self, text: str) -> str:
        """espeak-ng drops punctuation, so phonemize between punctuation marks and put it back."""
        out = []
        for piece in re.split(r'([,.;:!?—])', text):
            if not piece.strip():
                continue
            if re.fullmatch(r'[,.;:!?—]', piece):
                out.append(piece + ' ')
                continue
            ipa = subprocess.run(['espeak-ng', '-q', '--ipa', '-v', 'en-us', piece.strip()],
                                 capture_output=True, text=True, check=True).stdout
            ipa = ' '.join(ipa.split()).replace('ʲ', 'j').replace('r', 'ɹ').replace('x', 'k').replace('ɬ', 'l')
            out.append(ipa)
        return ''.join(out).strip()

    def speak(self, text: str, speed: float = 1.0) -> np.ndarray:
        tokens = [self.vocab[c] for c in self.phonemes(text) if c in self.vocab][:509]
        audio = self.session.run(None, {
            'input_ids': np.array([[0, *tokens, 0]], dtype=np.int64),
            'style': self.styles[len(tokens)].astype(np.float32),
            'speed': np.array([speed], dtype=np.float32)})[0]
        return np.asarray(audio, dtype=np.float32).reshape(-1)


def write_wav(path: str, audio: np.ndarray):
    with wave.open(path, 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes((np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())


if __name__ == '__main__':
    import sys
    engine = Kokoro()
    print(engine.phonemes(sys.argv[2]))
    sound = engine.speak(sys.argv[2])
    write_wav(sys.argv[1], sound)
    print(f'{len(sound) / RATE:.2f}s peak={np.abs(sound).max():.2f}')
