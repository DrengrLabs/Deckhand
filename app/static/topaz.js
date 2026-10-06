// Topaz signature pad support via the Topaz SigWeb service.
//
// SigWeb is a small Topaz program installed on the computer; it drives the
// pad and answers on http://tablet.sigwebtablet.com:47289 (that name always
// points back at this same computer, 127.0.0.1). These are the same calls
// Topaz's own SigWebTablet.js makes (TabletState, ClearSignature,
// TotalPoints, SigImage...), written as small async helpers so the app
// doesn't need that file's global variables and blocking requests.
//
// If SigWeb isn't installed, topazAvailable() simply resolves false and
// the signature box keeps working with mouse / touch / stylus.

const TOPAZ_BASE = "http://tablet.sigwebtablet.com:47289/SigWeb/";

async function topazCall(path, { method = "GET", blob = false, timeoutMs = 3000 } = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const url = TOPAZ_BASE + path + (method === "GET" ? `?noCache=${Date.now()}${Math.random()}` : "");
    const res = await fetch(url, { method, signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) throw new Error(`SigWeb ${path}: ${res.status}`);
    return blob ? res.blob() : (await res.text()).replace(/^"|"$/g, "").trim();
  } finally {
    clearTimeout(timer);
  }
}

const topazGet = (p) => topazCall(p);
const topazSet = (p) => topazCall(p, { method: "POST" });
const topazInt = async (p) => parseInt(await topazGet(p), 10) || 0;

// True when the SigWeb service is running on this computer.
async function topazAvailable() {
  try {
    await topazCall("TabletState", { timeoutMs: 1500 });
    return true;
  } catch (e) {
    return false;
  }
}

function topazBlobToImage(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = (e) => { URL.revokeObjectURL(url); reject(e); };
    img.src = url;
  });
}

// One capture session drawing live ink into a <canvas>.
// Usage: const s = await topazStart(canvas); ... await s.finish() / s.stop()
async function topazStart(canvas) {
  const ctx = canvas.getContext("2d");
  await topazSet(`DisplayXSize/${canvas.width}`);
  await topazSet(`DisplayYSize/${canvas.height}`);
  await topazSet("TabletState/0");          // reset any session left open
  await topazGet("ClearSignature");
  await topazSet("TabletState/1");          // start capturing from the pad
  if ((await topazInt("TabletState")) !== 1) {
    await topazSet("TabletState/0").catch(() => {});
    throw new Error("SigWeb is installed but no Topaz pad was found. Check the pad's USB cable and try again.");
  }

  let stopped = false;
  let lastPoints = 0;
  let busy = false;
  // Mirror what's being signed on the pad into the on-screen box.
  const timer = setInterval(async () => {
    if (stopped || busy) return;
    busy = true;
    try {
      const points = await topazInt("TotalPoints");
      if (points !== lastPoints) {
        lastPoints = points;
        const img = await topazBlobToImage(await topazCall("SigImage/0", { blob: true }));
        if (!stopped) {
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          ctx.drawImage(img, 0, 0);
        }
      }
    } catch (e) {
      /* a missed refresh is harmless; the next tick retries */
    } finally {
      busy = false;
    }
  }, 120);

  async function stop() {
    if (stopped) return;
    stopped = true;
    clearInterval(timer);
    await topazSet("TabletState/0").catch(() => {});
    await topazGet("LcdClear").catch(() => {});
  }

  return {
    async clear() {
      lastPoints = 0;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      await topazGet("ClearSignature");
    },
    async pointCount() {
      return topazInt("TotalPoints");
    },
    // Ends the session and draws the final signature into the canvas,
    // with the white background made transparent so it stamps cleanly.
    async finish() {
      const points = await topazInt("TotalPoints");
      if (points === 0) throw new Error("Nothing was signed on the pad yet.");
      clearInterval(timer);
      stopped = true;
      await topazSet(`ImageXSize/${canvas.width}`);
      await topazSet(`ImageYSize/${canvas.height}`);
      await topazSet("ImagePenWidth/5");
      const img = await topazBlobToImage(await topazCall("SigImage/1", { blob: true }));
      await topazSet("TabletState/0").catch(() => {});
      await topazGet("LcdClear").catch(() => {});
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      const data = ctx.getImageData(0, 0, canvas.width, canvas.height);
      const px = data.data;
      for (let i = 0; i < px.length; i += 4) {
        if (px[i] > 235 && px[i + 1] > 235 && px[i + 2] > 235) px[i + 3] = 0;
      }
      ctx.putImageData(data, 0, 0);
    },
    stop,
  };
}
