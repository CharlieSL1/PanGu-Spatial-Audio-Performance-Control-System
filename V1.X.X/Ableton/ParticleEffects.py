import asyncio
import websockets
import json
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import time

class ParticleWebSocketHandler:
    def __init__(self, port=8765):
        self.port = port
        self.clients = set()
        self.latest_hand_data = {}
        self.running = False
        self.server = None
        
    async def register_client(self, websocket):
        self.clients.add(websocket)
        print(f"粒子系统客户端已连接 (总数: {len(self.clients)})")
        if self.latest_hand_data:
            await websocket.send(json.dumps(self.latest_hand_data))
    
    async def unregister_client(self, websocket):
        self.clients.discard(websocket)
        print(f"粒子系统客户端已断开 (剩余: {len(self.clients)})")
    
    async def handle_client(self, websocket, path=None):
        await self.register_client(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    if data.get('type') == 'ping':
                        await websocket.send(json.dumps({'type': 'pong'}))
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    print(f"处理客户端消息时出错: {e}")
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"WebSocket连接错误: {e}")
        finally:
            await self.unregister_client(websocket)
    
    def update_hand_data(self, hand_data_list):
        if not hand_data_list:
            self.latest_hand_data = {
                'type': 'hand_data',
                'openness': 0.5,
                'pinch': 0.0,
                'hand_count': 0,
                'timestamp': time.time()
            }
        else:
            total_openness = 0
            total_pinch = 0
            for hand_data in hand_data_list:
                total_openness += hand_data.get('openness', 0.5)
                total_pinch += hand_data.get('pinch', 0.0)
            
            avg_openness = total_openness / len(hand_data_list)
            avg_pinch = total_pinch / len(hand_data_list)
            
            self.latest_hand_data = {
                'type': 'hand_data',
                'openness': float(avg_openness),
                'pinch': float(avg_pinch),
                'hand_count': len(hand_data_list),
                'hands': [
                    {
                        'id': h.get('hand_id', 0),
                        'openness': float(h.get('openness', 0.5)),
                        'pinch': float(h.get('pinch', 0.0)),
                        'palm_x': float(h.get('palm_x', 0.5)),
                        'palm_y': float(h.get('palm_y', 0.5)),
                        'palm_z': float(h.get('palm_z', 0.0))
                    }
                    for h in hand_data_list
                ],
                'timestamp': time.time()
            }
        
        if self.clients and hasattr(self, 'loop') and self.loop and not self.loop.is_closed():
            message = json.dumps(self.latest_hand_data)
            disconnected = set()
            for client in self.clients:
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        client.send(message),
                        self.loop
                    )
                except Exception as e:
                    print(f"发送消息到客户端失败: {e}")
                    disconnected.add(client)
            
            for client in disconnected:
                self.clients.discard(client)
    
    async def start_server(self):
        try:
            print(f"正在启动粒子系统WebSocket服务器 ws://localhost:{self.port}...")
            async with websockets.serve(self.handle_client, "127.0.0.1", self.port):
                self.running = True
                print(f"粒子系统WebSocket服务器已启动 ws://localhost:{self.port}")
                await asyncio.Future()
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"错误: 端口 {self.port} 已被占用，请关闭占用该端口的程序")
            else:
                print(f"WebSocket服务器启动失败: {e}")
            self.running = False
        except Exception as e:
            print(f"WebSocket服务器启动失败: {e}")
            self.running = False
    
    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.start_server())
    
    def start(self):
        if not self.running:
            self.server_thread = threading.Thread(target=self.run, daemon=True)
            self.server_thread.start()
            max_wait = 10
            waited = 0
            while not self.running and waited < max_wait:
                time.sleep(0.1)
                waited += 0.1
            if self.running:
                print(f"WebSocket服务器已就绪")
            else:
                print(f"警告: WebSocket服务器启动超时")
    
    def stop(self):
        self.running = False
        if hasattr(self, 'loop') and self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)


class ParticleHTTPHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        html_path = Path(__file__).parent / 'particle_system.html'
        self.html_path = html_path
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        if self.path == '/' or self.path == '/particle_system.html':
            try:
                with open(self.html_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'HTML file not found')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass


class ParticleSystemServer:
    def __init__(self, ws_port=8765, http_port=8766):
        self.ws_port = ws_port
        self.http_port = http_port
        self.ws_handler = ParticleWebSocketHandler(port=ws_port)
        self.http_server = None
        self.http_thread = None
    
    def start(self):
        self.ws_handler.start()
        
        try:
            self.http_server = HTTPServer(
                ('localhost', self.http_port),
                ParticleHTTPHandler
            )
            self.http_thread = threading.Thread(
                target=self.http_server.serve_forever,
                daemon=True
            )
            self.http_thread.start()
            print(f"粒子系统HTTP服务器启动在 http://localhost:{self.http_port}")
            print(f"在浏览器中打开: http://localhost:{self.http_port}/particle_system.html")
        except Exception as e:
            print(f"HTTP服务器启动失败: {e}")
    
    def update_hand_data(self, hand_data_list):
        self.ws_handler.update_hand_data(hand_data_list)
    
    def stop(self):
        self.ws_handler.stop()
        if self.http_server:
            self.http_server.shutdown()


_particle_server = None

def get_particle_server():
    global _particle_server
    if _particle_server is None:
        _particle_server = ParticleSystemServer()
    return _particle_server

def start_particle_system():
    server = get_particle_server()
    server.start()
    return server

def update_particle_hand_data(hand_data_list):
    server = get_particle_server()
    server.update_hand_data(hand_data_list)

