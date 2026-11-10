"""Record what OpenCode sends to the model, without storing credentials.

OpenCode is pointed at this local reverse proxy through the provider's baseURL in the
disposable profile's global configuration. The proxy forwards each request unchanged
to the real endpoint and appends one JSON line per request with the request body, the
reassembled response text and tool calls, and timings. Request and response headers
(which carry the login) are forwarded but never written to disk.
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import urllib.error
import urllib.request

HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
       'transfer-encoding', 'upgrade', 'host', 'content-length', 'accept-encoding'}

SAFE_HEADERS = {'x-opencode-session', 'x-opencode-session-id', 'x-session-id', 'x-opencode-client', 'user-agent'}


def summarize_stream(raw: bytes) -> dict:
    """Reassemble an OpenAI-style or Anthropic-style SSE (or plain JSON) completion."""
    text, reasoning, calls, finish, usage, model = [], [], {}, None, None, None
    body = raw.decode('utf-8', 'replace')
    events = []
    if body.lstrip().startswith('{'):
        try:
            events = [json.loads(body)]
        except ValueError:
            pass
    else:
        for line in body.split('\n'):
            if line.startswith('data:') and line[5:].strip() not in ('', '[DONE]'):  # 'event:' lines are redundant
                try:
                    events.append(json.loads(line[5:]))
                except ValueError:
                    pass
    for event in events:
        # Anthropic-style stream (message_start, content_block_*, message_delta) or message.
        kind = event.get('type')
        if kind == 'message_start':
            message = event.get('message') or {}
            model, usage = message.get('model') or model, message.get('usage') or usage
            continue
        if kind == 'content_block_start':
            block = event.get('content_block') or {}
            if block.get('type') == 'tool_use':
                calls[event.get('index', 0)] = {'id': block.get('id'), 'name': block.get('name', ''), 'arguments': ''}
            continue
        if kind == 'content_block_delta':
            delta = event.get('delta') or {}
            if delta.get('type') == 'text_delta':
                text.append(delta.get('text', ''))
            elif delta.get('type') == 'thinking_delta':
                reasoning.append(delta.get('thinking', ''))
            elif delta.get('type') == 'input_json_delta' and event.get('index', 0) in calls:
                calls[event.get('index', 0)]['arguments'] += delta.get('partial_json', '')
            continue
        if kind == 'message_delta':
            finish = (event.get('delta') or {}).get('stop_reason') or finish
            usage = {**(usage or {}), **(event.get('usage') or {})}
            continue
        if kind == 'message' and isinstance(event.get('content'), list):
            model, usage, finish = event.get('model') or model, event.get('usage') or usage, event.get('stop_reason')
            for index, block in enumerate(event['content']):
                if block.get('type') == 'text':
                    text.append(block.get('text', ''))
                elif block.get('type') == 'tool_use':
                    calls[index] = {'id': block.get('id'), 'name': block.get('name', ''),
                                    'arguments': json.dumps(block.get('input'))}
            continue
        model = event.get('model') or model
        usage = event.get('usage') or usage
        for choice in event.get('choices') or []:
            delta = choice.get('delta') or choice.get('message') or {}
            if delta.get('content'):
                text.append(delta['content'])
            for key in ('reasoning_content', 'reasoning'):
                if isinstance(delta.get(key), str):
                    reasoning.append(delta[key])
            for call in delta.get('tool_calls') or []:
                slot = calls.setdefault(call.get('index', 0), {'id': None, 'name': '', 'arguments': ''})
                slot['id'] = call.get('id') or slot['id']
                function = call.get('function') or {}
                slot['name'] += function.get('name') or ''
                slot['arguments'] += function.get('arguments') or ''
            finish = choice.get('finish_reason') or finish
    return {'model': model, 'text': ''.join(text), 'reasoning_chars': len(''.join(reasoning)),
            'tool_calls': [calls[i] for i in sorted(calls)], 'finish_reason': finish, 'usage': usage}


class Handler(BaseHTTPRequestHandler):
    upstream = ''
    log_path = ''
    lock = threading.Lock()
    sequence = 0
    protocol_version = 'HTTP/1.1'

    def log_message(self, _format, *_args):
        pass

    def _relay(self):
        length = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(length) if length else None
        with Handler.lock:
            Handler.sequence += 1
            sequence = Handler.sequence
        started = time.time()
        # The provider base URL ends in /v1 on both sides, so keep only what follows it.
        suffix = self.path.split('/v1', 1)[1] if '/v1' in self.path else self.path
        headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
        request = urllib.request.Request(Handler.upstream + suffix, data=body, headers=headers,
                                         method=self.command)
        record = {'seq': sequence, 'started': started, 'method': self.command, 'path': suffix,
                  # Header names only, plus the values of identifiers that are not credentials.
                  'header_names': sorted(k.lower() for k in self.headers.keys()),
                  'ids': {k.lower(): v for k, v in self.headers.items() if k.lower() in SAFE_HEADERS}}
        try:
            record['request'] = json.loads(body) if body else None
        except ValueError:
            record['request'] = {'unparsed_bytes': len(body or b'')}
        chunks = []
        try:
            try:
                response = urllib.request.urlopen(request, timeout=900)
            except urllib.error.HTTPError as error:
                response = error
            record['status'] = response.status
            self.send_response(response.status)
            for key, value in response.headers.items():
                if key.lower() not in HOP:
                    self.send_header(key, value)
            self.send_header('Transfer-Encoding', 'chunked')
            self.end_headers()
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                self.wfile.write(f'{len(chunk):x}\r\n'.encode() + chunk + b'\r\n')
                self.wfile.flush()
            self.wfile.write(b'0\r\n\r\n')
        except Exception as error:  # Record transport failures as evidence, then drop the client.
            record['error'] = f'{type(error).__name__}: {error}'
            self.close_connection = True
        raw = b''.join(chunks)
        record['finished'] = time.time()
        record['response'] = summarize_stream(raw) if record.get('status') == 200 else {
            'body': raw.decode('utf-8', 'replace')[:2000]}
        with Handler.lock, open(Handler.log_path, 'a') as log:
            log.write(json.dumps(record) + '\n')

    do_POST = do_GET = _relay


class QuietServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # Clients drop idle keep-alive connections; that is not evidence of anything.


def serve(upstream: str, log_path: str, port: int = 0) -> ThreadingHTTPServer:
    Handler.upstream, Handler.log_path, Handler.sequence = upstream.rstrip('/'), log_path, 0
    open(log_path, 'a').close()
    server = QuietServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--upstream', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    running = serve(args.upstream, args.log, args.port)
    print(running.server_port, flush=True)
    threading.Event().wait()
