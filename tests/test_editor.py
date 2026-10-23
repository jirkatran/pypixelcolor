"""Input validation and confirmed delivery for the local editor."""
import base64
from io import BytesIO
import unittest
from unittest.mock import AsyncMock, patch, MagicMock, call
from PIL import Image
from pypixelcolor.editor.__main__ import decode_frame
from pypixelcolor.editor.transport import send


def png(size=(96, 16)):
    output = BytesIO()
    Image.new('RGBA', size, (255, 80, 10, 255)).save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


class FrameTests(unittest.TestCase):
    def test_valid_frame_is_normalized_to_rgb(self):
        image = Image.open(BytesIO(decode_frame(png())))
        self.assertEqual(image.size, (96, 16))
        self.assertEqual(image.mode, 'RGB')
        self.assertEqual(image.getpixel((0, 0)), (255, 80, 10))

    def test_rejects_invalid_or_wrong_sized_frames(self):
        for value in [None, '', 'data:image/png;base64,!!!', png((16, 96))]:
            with self.subTest(value=str(value)[:40]), self.assertRaises(ValueError):
                decode_frame(value)


class DeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_ack_is_failure_and_disconnects(self):
        session = MagicMock()
        session.connect = AsyncMock()
        session.disconnect = AsyncMock()
        session.get_device_info.return_value = MagicMock(width=96, height=16)
        session.execute_command = AsyncMock(return_value=MagicMock(success=False, message='No ACK'))
        with patch('pypixelcolor.editor.transport.DeviceSession', return_value=session):
            with self.assertRaisesRegex(RuntimeError, 'No ACK'):
                await send('panel', '00')
        session.disconnect.assert_awaited_once()

    async def test_wrong_panel_is_not_sent(self):
        session = MagicMock()
        session.connect = AsyncMock()
        session.disconnect = AsyncMock()
        session.get_device_info.return_value = MagicMock(width=64, height=32)
        session.execute_command = AsyncMock()
        with patch('pypixelcolor.editor.transport.DeviceSession', return_value=session):
            with self.assertRaises(ValueError):
                await send('panel', '00')
        session.execute_command.assert_not_awaited()
        session.disconnect.assert_awaited_once()


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    def session(self, address):
        session = MagicMock()
        session.address = address
        session.is_connected = True
        session.connect = AsyncMock()
        session.disconnect = AsyncMock()
        session.get_device_info.return_value = MagicMock(width=96, height=16)
        session.execute_command = AsyncMock(return_value=MagicMock(success=True))
        return session

    async def test_switch_disconnects_old_panel_and_sends_only_to_selected(self):
        from pypixelcolor.editor.transport import PanelConnection
        first, second = self.session('first'), self.session('second')
        connection = PanelConnection()
        with patch('pypixelcolor.editor.transport.DeviceSession', side_effect=[first, second]):
            await connection.connect('first')
            await connection.send('second', '00')
        first.disconnect.assert_awaited_once()
        first.execute_command.assert_not_awaited()
        from pypixelcolor.commands.send_image import send_image_hex
        from pypixelcolor.commands.show_slot import show_slot
        self.assertEqual(second.execute_command.await_args_list, [
            call(show_slot, 1), call(send_image_hex, '00', '.png', save_slot=1)])
        self.assertEqual(connection.status(), {'connected': True, 'address': 'second'})

    async def test_same_panel_reuses_connection_and_disconnect_clears_status(self):
        from pypixelcolor.editor.transport import PanelConnection
        session = self.session('panel')
        connection = PanelConnection()
        with patch('pypixelcolor.editor.transport.DeviceSession', return_value=session) as factory:
            await connection.connect('panel')
            await connection.send('panel', '00')
        factory.assert_called_once()
        session.disconnect.assert_not_awaited()
        await connection.disconnect()
        self.assertEqual(connection.status(), {'connected': False, 'address': ''})

    async def test_lost_connection_is_reported_and_reconnected(self):
        from pypixelcolor.editor.transport import PanelConnection
        connection = PanelConnection()
        old = self.session('panel')
        old.is_connected = False
        connection.session = old
        self.assertFalse(connection.status()['connected'])
        new = self.session('panel')
        with patch('pypixelcolor.editor.transport.DeviceSession', return_value=new):
            await connection.connect('panel')
        new.connect.assert_awaited_once()
        self.assertTrue(connection.status()['connected'])


class MotionTests(unittest.TestCase):
    def test_valid_scrolling_text_and_speed(self):
        from pypixelcolor.editor.__main__ import validate_motion
        payload = dict(animation='scroll_left', text='AHOJ SVETE', speed=75,
                       size=12, color='#ff7338', background='#000000')
        result = validate_motion(payload)
        self.assertEqual(result['speed'], 75)
        self.assertEqual(result['color'], 'ff7338')
        self.assertNotIn('image', result)

    def test_rejects_invalid_motion_settings(self):
        from pypixelcolor.editor.__main__ import validate_motion
        payload = dict(animation='scroll_left', text='AHOJ', speed=60,
                       size=12, color='#ff7338', background='#000000')
        for change in [dict(speed=101), dict(speed=True), dict(text='a\nb'),
                       dict(text=''), dict(size=100), dict(color='#zzzzzz'),
                       dict(animation='unknown')]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_motion({**payload, **change})


class MotionDeliveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_scroll_uses_verified_native_defaults(self):
        from pypixelcolor.editor.transport import PanelConnection
        from pypixelcolor.commands.send_image import send_image_hex
        session = MagicMock()
        session.is_connected = True
        session.address = 'panel'
        session.execute_command = AsyncMock(return_value=MagicMock(success=True))
        connection = PanelConnection()
        connection.session = session
        text = 'DLOUHY TEXT KTERY SE NEVEJDE NA PANEL'
        await connection.handle(dict(action='send', address='panel', animation='scroll_left',
                                     text=text, speed=75, size=12, color='ff7338', background='000000'))
        args, kwargs = session.execute_command.call_args_list[1]
        from pypixelcolor.commands.send_text import send_text
        self.assertIs(args[0], send_text)
        self.assertEqual(args[1], text)
        self.assertEqual(kwargs['animation'], 'scroll_left')
        self.assertEqual(kwargs['speed'], 75)
        self.assertEqual(kwargs['save_slot'], 1)
        self.assertNotIn('font', kwargs)
        self.assertNotIn('bg_color', kwargs)
        from pypixelcolor.commands.show_slot import show_slot
        self.assertEqual(session.execute_command.await_args_list[0], call(show_slot, 1))


class SavedSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_selection_failure_is_reported(self):
        from pypixelcolor.editor.transport import PanelConnection
        connection = PanelConnection()
        connection.session = MagicMock()
        connection.session.execute_command = AsyncMock(
            return_value=MagicMock(success=False, message='No ACK'))
        with self.assertRaisesRegex(RuntimeError, 'No ACK'):
            await connection.prepare_saved_banner()
