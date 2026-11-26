"""Small, bounded protections for a single-instance demo deployment."""
from collections import deque
from threading import Lock
from time import monotonic
from starlette.responses import JSONResponse

MAX_BODY = 3 * 1024 * 1024

class ApiProtection:
    def __init__(self, app, limit=30, total_limit=300, window=60):
        self.app, self.limit, self.total_limit, self.window = app, limit, total_limit, window
        self.clients, self.total, self.lock = {}, deque(), Lock()

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/'):
            return await self.app(scope, receive, send)
        # Health checks and preflight should not consume the request budget.
        if scope['path'] != '/api/health' and scope['method'] != 'OPTIONS':
            now = monotonic()
            client = (scope.get('client') or ('unknown', 0))[0]
            with self.lock:
                while self.total and self.total[0] <= now - self.window:
                    self.total.popleft()
                for key in list(self.clients):
                    events = self.clients[key]
                    while events and events[0] <= now - self.window:
                        events.popleft()
                    if not events:
                        del self.clients[key]
                events = self.clients.get(client, deque())
                blocked = len(self.total) >= self.total_limit or len(events) >= self.limit
                if not blocked:
                    events.append(now)
                    self.clients[client] = events
                    self.total.append(now)
            if blocked:
                return await JSONResponse({'detail': 'Rate limit exceeded. Please try again later.'}, status_code=429, headers={'Retry-After': str(self.window)})(scope, receive, send)
        headers = dict(scope['headers'])
        try:
            length = int(headers.get(b'content-length', b'0'))
            if length < 0 or length > MAX_BODY:
                return await JSONResponse({'detail': 'Request body too large.'}, status_code=413)(scope, receive, send)
        except ValueError:
            return await JSONResponse({'detail': 'Invalid Content-Length.'}, status_code=400)(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            size += len(chunk)
            if size > MAX_BODY:
                return await JSONResponse({'detail': 'Request body too large.'}, status_code=413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get('more_body', False):
                break
        body = b''.join(chunks)
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': body, 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)
