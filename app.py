import os
import io
import base64
import serial
import serial.tools.list_ports
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageDraw

app = Flask(__name__)
printer = None

ESC = b'\x1b'
GS = b'\x1d'
DLE = b'\x10'


def get_available_ports():
    ports = serial.tools.list_ports.comports()
    return [{"device": p.device, "description": p.description} for p in ports]


def connect_printer(port_name, baudrate=9600):
    global printer
    try:
        if printer and printer.is_open:
            printer.close()
        printer = serial.Serial(port_name, baudrate=baudrate, timeout=1)
        return True, f"Connected to {port_name}"
    except Exception as e:
        return False, str(e)


def disconnect_printer():
    global printer
    if printer and printer.is_open:
        printer.close()
        printer = None
    return True, "Disconnected"


def is_connected():
    return printer is not None and printer.is_open


def send_command(data):
    if not is_connected():
        raise Exception("Printer not connected")
    printer.write(data)


def initialize_printer():
    send_command(ESC + b'@')
    send_command(ESC + b'a' + b'\x01')


def print_text(text, bold=False, underline=False, align="center", width=1, height=1, feed_lines=3, init=True):
    if init:
        initialize_printer()

    align_cmd = {"left": b'\x00', "center": b'\x01', "right": b'\x02'}
    send_command(ESC + b'a' + align_cmd.get(align, b'\x01'))

    mode = 0
    if bold:
        mode |= 0x08
    if underline:
        mode |= 0x80
    send_command(ESC + b'E' + bytes([mode]))

    if width > 1 or height > 1:
        send_command(GS + b'!' + bytes([(height - 1) << 4 | (width - 1)]))
    else:
        send_command(GS + b'!' + b'\x00')

    lines = text.split('\n')
    for line in lines:
        send_command(line.encode('utf-8'))
        send_command(b'\n')

    send_command(GS + b'!' + b'\x00')
    send_command(ESC + b'E' + b'\x00')

    if feed_lines > 0:
        send_command(ESC + b'd' + bytes([feed_lines]))


def print_image_base64(img_base64, init=True):
    if init:
        initialize_printer()
    data = img_base64
    if ',' in data:
        data = data.split(',', 1)[1]
    img_bytes = base64.b64decode(data)
    img = Image.open(io.BytesIO(img_bytes)).convert('1')
    img = img.resize((384, int(img.height * 384 / img.width)), Image.LANCZOS)
    pixels = img.load()
    w, h = img.size

    send_command(ESC + b'a' + b'\x01')

    header = GS + b'v0' + b'\x00'
    x_bytes = w // 8
    data_bytes = header + x_bytes.to_bytes(2, 'little') + h.to_bytes(2, 'little')

    for y in range(h):
        for x_byte in range(x_bytes):
            byte = 0
            for bit in range(8):
                if pixels[x_byte * 8 + bit, y] == 0:
                    byte |= (1 << (7 - bit))
            data_bytes += bytes([byte])

    send_command(data_bytes)
    send_command(b'\n\n\n')


def print_barcode(content, barcode_type=73, height=80, hri_position=2, init=True):
    if init:
        initialize_printer()
    send_command(ESC + b'a' + b'\x01')
    send_command(GS + b'h' + bytes([height]))
    send_command(GS + b'w' + b'\x02')
    send_command(GS + b'H' + bytes([hri_position]))
    send_command(GS + b'k' + bytes([barcode_type]) + bytes([len(content)]) + content.encode('ascii'))
    send_command(b'\n\n\n')


def print_qr_code(content, size=6, init=True):
    if init:
        initialize_printer()
    send_command(ESC + b'a' + b'\x01')
    send_command(GS + b'(' + b'k' + bytes([4]) + bytes([0]) + bytes([49]) + bytes([67]) + bytes([size]))
    data = content.encode('utf-8')
    send_command(GS + b'(' + b'k' + bytes([len(data) + 3]) + bytes([0]) + bytes([49]) + bytes([80]) + bytes([48]) + data)
    send_command(GS + b'(' + b'k' + bytes([3]) + bytes([0]) + bytes([49]) + bytes([81]) + bytes([48]))
    send_command(b'\n\n\n')


def print_combo(items, cut=False, feed_after=5):
    if not items:
        raise Exception("No items in receipt")
    initialize_printer()
    for item in items:
        itype = item.get('type')
        if itype == 'text':
            print_text(
                item.get('text', ''),
                bold=item.get('bold', False),
                underline=item.get('underline', False),
                align=item.get('align', 'center'),
                width=item.get('width', 1),
                height=item.get('height', 1),
                feed_lines=item.get('feed_lines', 1),
                init=False
            )
        elif itype == 'image':
            img = item.get('image', '')
            if img:
                print_image_base64(img, init=False)
        elif itype == 'barcode':
            print_barcode(
                item.get('content', ''),
                barcode_type=item.get('type', 73),
                height=item.get('height', 80),
                hri_position=item.get('hri_position', 2),
                init=False
            )
        elif itype == 'qr':
            print_qr_code(item.get('content', ''), size=item.get('size', 6), init=False)
        elif itype == 'feed':
            send_command(ESC + b'd' + bytes([min(int(item.get('lines', 3)), 255)]))
        elif itype == 'cut':
            send_command(GS + b'V' + b'\x00')
        elif itype == 'dl' or itype == 'dashed':
            send_command(b'- - - - - - - - - - - - - - - - - - - -\n')
    if cut:
        send_command(ESC + b'd' + bytes([max(min(feed_after, 99), 0)]))
        send_command(GS + b'V' + b'\x00')


def print_raster_image(img):
    img = img.convert('1')
    w, h = img.size
    x_bytes = w // 8
    header = GS + b'v0' + b'\x00' + x_bytes.to_bytes(2, 'little') + h.to_bytes(2, 'little')
    data = bytearray(header)
    pixels = img.load()
    for y in range(h):
        for x_byte in range(x_bytes):
            byte = 0
            for bit in range(8):
                if pixels[x_byte * 8 + bit, y] == 0:
                    byte |= (1 << (7 - bit))
            data.append(byte)
    send_command(bytes(data))


def run_head_cleaning(sheets=2, pattern="solid"):
    initialize_printer()
    for s in range(sheets):
        if pattern == "stripes":
            for block in range(10):
                stripe = Image.new('1', (384, 96), 1 if block % 2 else 0)
                print_raster_image(stripe)
                send_command(b'\n\n')
        else:
            for block in range(8):
                band = Image.new('1', (384, 128), 0)
                print_raster_image(band)
                send_command(b'\n\n')
        send_command(ESC + b'd' + bytes([8]))
        send_command(b'\n')
    send_command(ESC + b'd' + bytes([20]))


def _print_alignment_pattern():
    w = 384
    top = 5
    img = Image.new('1', (w, 400), 1)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, top - 1], fill=0)
    d.rectangle([0, 395, w - 1, 399], fill=0)
    d.rectangle([0, 0, 7, 399], fill=0)
    d.rectangle([w - 8, 0, w - 1, 399], fill=0)
    for y in range(top, 399, 32):
        d.line([8, y, w - 9, y], fill=0)
    for x in range(8, w - 8, 48):
        d.line([x, top, x, 399], fill=0)
    mid = w // 2
    for y in range(top, 399, 8):
        if (y // 8) % 2 == 0:
            d.line([mid, y, mid, min(y + 4, 399)], fill=0)
    d.rectangle([8, top, 40, 40], fill=0)
    d.rectangle([w - 41, top, w - 9, 40], fill=0)
    for yy in range(340, 380, 8):
        for xx in range(8, w - 8, 8):
            if (xx // 8 + yy // 8) % 2 == 0:
                d.rectangle([xx, yy, xx + 7, yy + 7], fill=0)
    print_raster_image(img)
    send_command(b'\n\n')


def run_printer_test():
    initialize_printer()
    send_command(ESC + b'a' + b'\x01')
    send_command(GS + b'!' + b'\x11')
    send_command(b'<< PRINTERMAX M58 TEST PAGE >>\n\n'.encode('utf-8'))
    send_command(GS + b'!' + b'\x00')

    send_command(ESC + b'a' + b'\x00')
    send_command(b'<LEFT>'.encode('utf-8') + b'\n')
    send_command(ESC + b'a' + b'\x01')
    send_command(b'<CENTER>'.encode('utf-8') + b'\n')
    send_command(ESC + b'a' + b'\x02')
    send_command(b'<RIGHT>'.encode('utf-8') + b'\n')
    send_command(b'\n')
    send_command(ESC + b'a' + b'\x01')
    send_command(b'--- 384px / 58mm print width ---\n'.encode('utf-8') + b'\n')

    _print_alignment_pattern()

    send_command(ESC + b'a' + b'\x01')
    send_command(b'BARCODE'.encode('utf-8') + b'\n')
    send_command(GS + b'h' + bytes([70]))
    send_command(GS + b'w' + b'\x02')
    send_command(GS + b'H' + b'\x02')
    send_command(GS + b'k' + b'\x49' + b'\x0c' + b'PRINTERMAX58'.encode('ascii'))
    send_command(b'\n\n')
    send_command(b'QR CODE'.encode('utf-8') + b'\n')
    send_command(GS + b'a' + b'\x01')
    send_command(GS + b'(' + b'k' + bytes([4]) + bytes([0]) + bytes([49]) + bytes([67]) + bytes([6]))
    payload = b'https://example.com/printermax'
    send_command(GS + b'(' + b'k' + bytes([len(payload) + 3]) + bytes([0]) + bytes([49]) + bytes([80]) + bytes([48]) + payload)
    send_command(GS + b'(' + b'k' + bytes([3]) + bytes([0]) + bytes([49]) + bytes([81]) + bytes([48]))
    send_command(b'\n\n\n')
    send_command(ESC + b'd' + bytes([20]))
    send_command(GS + b'V' + b'\x00')


def read_printer_status():
    if not is_connected():
        raise Exception("Printer not connected")
    printer.reset_input_buffer()
    send_command(DLE + b'EOT' + b'\x01')
    b1 = printer.read(1)
    send_command(DLE + b'EOT' + b'\x04')
    b2 = printer.read(1)
    rp = ord(b1) if b1 else None
    pp = ord(b2) if b2 else None

    online = "unknown"
    if rp is not None:
        online = "yes" if (rp & 0x40) == 0 else "no"

    paper_status = "unknown"
    if pp is not None:
        if pp & 0x08:
            paper_status = "out of paper"
        elif pp & 0x20:
            paper_status = "low"
        elif pp & 0x02:
            paper_status = "out of paper"
        else:
            paper_status = "ok"

    return {
        "online": online,
        "paper_status": paper_status,
        "raw_printer": ("%02X" % rp) if rp is not None else "--",
        "raw_paper": ("%02X" % pp) if pp is not None else "--",
    }


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/ports')
def api_ports():
    return jsonify(get_available_ports())


@app.route('/api/connect', methods=['POST'])
def api_connect():
    data = request.json
    port = data.get('port')
    baudrate = data.get('baudrate', 9600)
    ok, msg = connect_printer(port, baudrate)
    return jsonify({"success": ok, "message": msg})


@app.route('/api/disconnect', methods=['POST'])
def api_disconnect():
    ok, msg = disconnect_printer()
    return jsonify({"success": ok, "message": msg})


@app.route('/api/status')
def api_status():
    return jsonify({"connected": is_connected()})


@app.route('/api/feed', methods=['POST'])
def api_feed():
    try:
        data = request.json
        lines = data.get('lines', 3)
        initialize_printer()
        send_command(ESC + b'd' + bytes([lines]))
        return jsonify({"success": True, "message": f"Fed {lines} lines"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/cut', methods=['POST'])
def api_cut():
    try:
        initialize_printer()
        send_command(GS + b'V' + b'\x00')
        return jsonify({"success": True, "message": "Paper cut"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/print/text', methods=['POST'])
def api_print_text():
    try:
        data = request.json
        text = data.get('text', '')
        print_text(
            text,
            bold=data.get('bold', False),
            underline=data.get('underline', False),
            align=data.get('align', 'center'),
            width=data.get('width', 1),
            height=data.get('height', 1),
            feed_lines=data.get('feed_lines', 3)
        )
        return jsonify({"success": True, "message": "Text printed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/print/image', methods=['POST'])
def api_print_image():
    try:
        data = request.json
        img_data = data.get('image', '')
        if not img_data:
            return jsonify({"success": False, "message": "No image data"})
        print_image_base64(img_data)
        return jsonify({"success": True, "message": "Image printed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/print/barcode', methods=['POST'])
def api_print_barcode():
    try:
        data = request.json
        print_barcode(
            data.get('content', '123456789'),
            barcode_type=data.get('type', 73),
            height=data.get('height', 80),
            hri_position=data.get('hri_position', 2)
        )
        return jsonify({"success": True, "message": "Barcode printed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/print/qrcode', methods=['POST'])
def api_print_qrcode():
    try:
        data = request.json
        print_qr_code(
            data.get('content', 'https://example.com'),
            size=data.get('size', 6)
        )
        return jsonify({"success": True, "message": "QR code printed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/print/combo', methods=['POST'])
def api_print_combo():
    try:
        data = request.json
        items = data.get('items', [])
        if not items:
            return jsonify({"success": False, "message": "Add at least one block"})
        print_combo(
            items,
            cut=data.get('cut', False),
            feed_after=data.get('feed_after', 5)
        )
        return jsonify({"success": True, "message": f"Printed {len(items)} block(s) in one receipt"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/tools/clean', methods=['POST'])
def api_tools_clean():
    try:
        data = request.json
        sheets = data.get('sheets', 2)
        pattern = data.get('pattern', 'solid')
        run_head_cleaning(sheets=sheets, pattern=pattern)
        return jsonify({"success": True, "message": f"Head cleaning started ({sheets} sheet(s), {pattern} pattern)"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/tools/test', methods=['POST'])
def api_tools_test():
    try:
        run_printer_test()
        return jsonify({"success": True, "message": "Test page printed"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/api/tools/status', methods=['GET'])
def api_tools_status():
    try:
        info = read_printer_status()
        info["success"] = True
        return jsonify(info)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
