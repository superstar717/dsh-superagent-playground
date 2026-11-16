#!/usr/bin/env python3
# analyze-sample.py — pull encoder-related thread signatures out of a `sample` dump.
# usage: analyze-sample.py <renderer-sample.txt> [...]
import re, sys, os

SIGS = [
    ('vt_hw_encode', r'VTCompressionSession|VTBundleEncodeSession|VTVideoEncodeAccelerator|VideoToolboxVideoEncoder|vtcompressionencoder|VTEncoderSession'),
    ('vt_sw_encode (OS encoder)', r'VCPixelTransferSession|VTSoftwareEncode|is_software_codec|SWVideoEncoder'),
    ('openh264_sw', r'openh264|Wels|OpenH264Encoder'),
    ('libvpx_vp9_sw', r'vpx_enc|vp9_encodeframe|libvpx|VP9|vp9_svc|VpxVideoEncoder'),
    ('mediarecorder_pipeline', r'VideoEncoderEncoder|EncoderStreamFactory|MediaRecorder|VideoStreamEncoder'),
    ('canvas_bake', r'drawImage|CanvasRenderingContext2D|SharedCanvasImageProvider|Canvas2D'),
    ('capture_pipeline', r'desktopCapturer|ScreenCaptureKit|SCStream|CaptureStream'),
]
for path in sys.argv[1:]:
    if not os.path.exists(path):
        print(f'{path}: MISSING')
        continue
    text = open(path, errors='replace').read()
    print(f'== {os.path.basename(os.path.dirname(path))} ({len(text)} bytes)')
    for name, pat in SIGS:
        hits = re.findall(pat, text)
        print(f'  {name}: {len(hits)}')
    # show the top 6 hottest stacks' first frames for context
    stacks = re.findall(r'Call graph:\n(.*?)\n\nTotal number', text, re.S)
    if not stacks:
        # sample format: header ... Call graph: ... then per-thread sections
        m = re.search(r'Call graph:\n(.*)', text, re.S)
        body = m.group(1) if m else text
    else:
        body = stacks[0]
    heads = [l for l in body.splitlines() if re.match(r'\s{6,}\d{3,}', l)][:14]
    for h in heads:
        print('  ' + h.strip()[:150])
