const { contextBridge, ipcRenderer, desktopCapturer } = require('electron');
contextBridge.exposeInMainWorld('__run', async () => {
  ipcRenderer.send('test-result', { started: true });
  try {
    const sources = await desktopCapturer.getSources({ types: ['screen'], thumbnailSize: { width: 320, height: 200 } });
    const primary = sources[0];
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { mandatory: { chromeMediaSource: 'desktop', chromeMediaSourceId: primary.id, maxWidth: 3840, maxHeight: 2160, maxFrameRate: 30 } },
    });
    const track = stream.getVideoTracks()[0];
    const settings = track.getSettings();
    const rec = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
    const chunks = [];
    rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
    rec.start(500);
    await new Promise(r => setTimeout(r, 3000));
    rec.stop();
    await new Promise(r => rec.onstop = r);
    track.stop();
    const blob = new Blob(chunks, { type: 'video/webm' });
    const buf = new Uint8Array(await blob.arrayBuffer());
    ipcRenderer.send('test-result', { settings, mime: rec.mimeType, bytes: buf.length, b64: Buffer.from(buf).toString('base64') });
  } catch (e) {
    ipcRenderer.send('test-result', { error: e.message });
  }
});
