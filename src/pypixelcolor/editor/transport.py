"""Persistent BLE worker; macOS Bluetooth runs on this process's main thread."""
import asyncio
import json
import sys

from ..commands.send_image import send_image_hex
from ..commands.send_text import send_text
from ..commands.show_slot import show_slot
from ..lib.device_session import DeviceSession
from ..scanner import scan_devices


class PanelConnection:
    def __init__(self):
        self.session = None

    def status(self):
        connected = bool(self.session and self.session.is_connected)
        return {'connected': connected,
                'address': self.session.address if connected else ''}

    async def disconnect(self):
        session, self.session = self.session, None
        if session:
            await session.disconnect()
        return self.status()

    async def connect(self, address):
        if self.status()['address'] == address:
            return self.status()
        await self.disconnect()
        session = DeviceSession(address)
        try:
            await session.connect()
            info = session.get_device_info()
            if (info.width, info.height) != (96, 16):
                raise ValueError(f'Panel má {info.width} × {info.height} px. Editor podporuje 96 × 16.')
        except Exception:
            await session.disconnect()
            raise
        self.session = session
        return self.status()

    async def prepare_saved_banner(self):
        result = await self.session.execute_command(show_slot, 1)
        if not result.success:
            raise RuntimeError(result.message or 'Panel nepotvrdil nastavení seznamu s jediným bannerem.')

    async def send(self, address, image):
        await self.connect(address)
        # Program list must be declared before uploading every listed slot.
        await self.prepare_saved_banner()
        result = await self.session.execute_command(send_image_hex, image, '.png', save_slot=1)
        if not result.success:
            raise RuntimeError(result.message or 'Panel nepotvrdil přijetí obrázku.')
        return {**self.status(), 'message': 'Banner byl odeslán a uložen do paměti panelu (slot 1).'}

    async def send_scrolling_text(self, request):
        await self.connect(request['address'])
        await self.prepare_saved_banner()
        # This panel was visually verified with the default 16 px native font.
        # Omit custom font/background properties, which produced corrupt glyphs.
        result = await self.session.execute_command(
            send_text, request['text'], animation='scroll_left',
            speed=request['speed'], color=request['color'], save_slot=1)
        if not result.success:
            raise RuntimeError(result.message or 'Panel nepotvrdil přijetí textu.')
        return {**self.status(), 'message': 'Text s posunem doleva byl odeslán a uložen do paměti panelu (slot 1).'}

    async def handle(self, request):
        action = request['action']
        if action == 'scan':
            devices = await scan_devices(timeout=6)
            return {'devices': [{'name': d.name, 'address': d.address} for d in devices],
                    **self.status()}
        if action == 'status':
            return self.status()
        if action == 'disconnect':
            return await self.disconnect()
        if action == 'connect':
            return await self.connect(request['address'])
        if action == 'send':
            if request.get('animation') == 'scroll_left':
                return await self.send_scrolling_text(request)
            return await self.send(request['address'], request['image'])
        raise ValueError('Neznámá operace.')


async def send(address, image):
    connection = PanelConnection()
    try:
        await connection.send(address, image)
    finally:
        await connection.disconnect()


async def worker():
    connection = PanelConnection()
    try:
        while True:
            line = await asyncio.to_thread(sys.stdin.readline)
            if not line:
                break
            try:
                data = await asyncio.wait_for(connection.handle(json.loads(line)), timeout=40)
                response = {'ok': True, **data}
            except Exception as exc:
                response = {'ok': False, 'error': str(exc) or 'Operace Bluetooth překročila časový limit.',
                            **connection.status()}
            print(json.dumps(response), flush=True)
    finally:
        await connection.disconnect()


if __name__ == '__main__':
    asyncio.run(worker())
