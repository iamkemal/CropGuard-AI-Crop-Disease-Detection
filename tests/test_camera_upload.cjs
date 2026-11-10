// Camera lifecycle tests. Run with Node 18+; no npm packages are required.
// Media, canvas, and DOM objects are simulated. Real-device checks are separate.
const assert = require("node:assert/strict");
const { test } = require("node:test");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const vm = require("node:vm");
const { File } = require("node:buffer");

const root = resolve(__dirname, "..");
const source = readFileSync(resolve(root, "app/static/js/upload-preview.js"), "utf8");
const markup = readFileSync(resolve(root, "app/templates/farmer/diagnose.html"), "utf8");
const settle = () => new Promise((resolve) => setImmediate(resolve));

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function media() {
  const track = { stops: 0, stop() { this.stops += 1; } };
  return { track, getTracks: () => [track] };
}

function environment(options = {}) {
  class Element extends EventTarget {
    constructor(id, attributes = "") {
      super();
      this.id = id;
      this.hidden = /\bhidden\b/.test(attributes);
      this.disabled = /\bdisabled\b/.test(attributes);
      this.textContent = "";
      this.files = [];
      this.open = false;
      this.clicks = 0;
    }
    click() {
      if (!this.disabled) { this.clicks += 1; this.dispatchEvent(new Event("click")); }
    }
    focus() { state.focus = this.id; }
    removeAttribute(name) { delete this[name]; }
    set value(value) { if (value === "") this.files = []; }
  }
  const state = { focus: null, requests: [], streams: [], revoked: [], urls: 0, canvases: [] };
  const elements = new Map();
  for (const match of markup.matchAll(/<[a-z][a-z0-9-]*\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    elements.set(match[2], new Element(match[2], match[1]));
  }
  const get = (id) => elements.get(id);
  const dialog = get("cameraDialog");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => {
    dialog.open = false;
    setImmediate(() => dialog.dispatchEvent(new Event("close")));
  };
  if (options.noDialog) delete dialog.showModal;
  get("cameraVideo").videoWidth = 3840;
  get("cameraVideo").videoHeight = 2160;
  get("cameraVideo").play = async () => {};
  const document = new EventTarget();
  document.getElementById = get;
  document.hidden = false;
  document.createElement = (tag) => {
    assert.equal(tag, "canvas");
    const canvas = {
      getContext: () => ({ drawImage() {} }),
      toBlob(callback, type, quality) {
        this.type = type;
        this.quality = quality;
        if (options.blobDeferred) options.blobDeferred.push(callback);
        else callback(options.nullBlob ? null : new Blob(["photo bytes"], { type: options.png ? "image/png" : type }));
      },
    };
    state.canvases.push(canvas);
    return canvas;
  };
  const window = new EventTarget();
  window.isSecureContext = options.secure !== false;
  const navigator = { mediaDevices: { getUserMedia: async (constraints) => {
    state.requests.push(constraints);
    if (options.permission) return options.permission.promise;
    if (options.error) throw options.error;
    const stream = media();
    state.streams.push(stream);
    return stream;
  } } };
  class DataTransfer {
    constructor() {
      if (options.transferError) throw new Error("FileList assignment unavailable");
      this.files = [];
      this.items = { add: (file) => this.files.push(file) };
    }
  }
  const URL = {
    createObjectURL: () => `blob:preview-${++state.urls}`,
    revokeObjectURL: (url) => state.revoked.push(url),
  };
  vm.runInNewContext(source, { document, window, navigator, URL, File, Blob, DataTransfer, Event, console });
  const upload = () => {
    const file = new File(["original"], "existing.png", { type: "image/png" });
    get("cropImage").files = [file];
    get("cropImage").dispatchEvent(new Event("change"));
    return file;
  };
  const open = async () => { get("takePicture").click(); await settle(); };
  return { state, get, document, window, open, upload };
}

test("choose-photo opens the picker and uses the existing preview", () => {
  const e = environment();
  assert.equal(e.state.requests.length, 0);
  e.get("choosePhoto").click();
  assert.equal(e.get("cropImage").clicks, 1);
  const file = e.upload();
  assert.equal(e.get("cropImage").files[0], file);
  assert.equal(e.get("imagePreviewWrap").hidden, false);
  assert.match(e.get("photoStatus").textContent, /existing.png/);
});

test("camera starts only on request and cancellation preserves an uploaded photo", async () => {
  const e = environment();
  const file = e.upload();
  const preview = e.get("cropImagePreview").src;
  await e.open();
  assert.equal(e.state.requests[0].audio, false);
  assert.equal(e.state.requests[0].video.facingMode.ideal, "environment");
  e.get("cancelCamera").click();
  await settle();
  assert.equal(e.state.streams[0].track.stops, 1);
  assert.equal(e.get("cameraDialog").open, false);
  assert.equal(e.get("cropImage").files[0], file);
  assert.equal(e.get("cropImagePreview").src, preview);
});

test("capture is reviewed before attaching a JPEG to the existing upload field", async () => {
  const e = environment();
  await e.open();
  e.get("capturePhoto").click();
  assert.equal(e.get("cropImage").files.length, 0);
  assert.equal(e.state.streams[0].track.stops, 1);
  assert.equal(e.get("cameraSnapshot").hidden, false);
  assert.equal(e.state.canvases[0].width, 2048);
  assert.equal(e.state.canvases[0].height, 1152);
  assert.equal(e.state.canvases[0].type, "image/jpeg");
  e.get("usePhoto").click();
  const [file] = e.get("cropImage").files;
  assert.equal(file.type, "image/jpeg");
  assert.match(file.name, /^crop-camera-\d+\.jpg$/);
  assert.match(markup, /id="cropImage" name="crop_image"/);
  assert.equal(e.get("imagePreviewWrap").hidden, false);
  assert.equal(e.get("cameraDialog").open, false);
  e.get("removePhoto").click();
  assert.equal(e.get("cropImage").files.length, 0);
  assert.equal(e.get("imagePreviewWrap").hidden, true);
  assert.ok(e.state.revoked.length >= 2);
});

test("retake opens a new stream and never commits an unaccepted photo", async () => {
  const e = environment();
  const file = e.upload();
  await e.open();
  e.get("capturePhoto").click();
  e.get("retakePhoto").click();
  await settle();
  assert.equal(e.state.streams.length, 2);
  assert.equal(e.get("cropImage").files[0], file);
  assert.equal(e.get("cameraSnapshot").hidden, true);
  assert.equal(e.get("usePhoto").hidden, true);
  e.get("closeCamera").click();
  assert.equal(e.state.streams[1].track.stops, 1);
});

test("permission denial explains recovery without discarding the current photo", async () => {
  const e = environment({ error: { name: "NotAllowedError" } });
  const file = e.upload();
  await e.open();
  assert.match(e.get("cameraError").textContent, /permission/);
  assert.equal(e.get("capturePhoto").disabled, true);
  e.get("closeCamera").click();
  e.get("choosePhoto").click();
  assert.equal(e.get("cropImage").files[0], file);
  assert.equal(e.get("cropImage").clicks, 1);
});

test("a permission response arriving after cancel is immediately stopped", async () => {
  const permission = deferred();
  const e = environment({ permission });
  e.get("takePicture").click();
  e.get("cancelCamera").click();
  const late = media();
  permission.resolve(late);
  await settle();
  assert.equal(late.track.stops, 1);
  assert.equal(e.get("cameraVideo").srcObject, null);
  assert.equal(e.get("cameraDialog").open, false);
});

test("a stale photo encoder callback cannot affect a reopened camera", async () => {
  const callbacks = [];
  const e = environment({ blobDeferred: callbacks });
  await e.open();
  e.get("capturePhoto").click();
  e.get("cancelCamera").click();
  // Simulate reopening before the old dialog-close event is delivered.
  e.get("takePicture").click();
  await settle();
  callbacks[0](new Blob(["old photo"], { type: "image/jpeg" }));
  assert.equal(e.get("cameraDialog").open, true);
  assert.equal(e.get("cameraSnapshot").hidden, true);
  assert.equal(e.state.streams[1].track.stops, 0);
  e.get("closeCamera").click();
});

test("hiding the page and leaving it release camera resources", async () => {
  const e = environment();
  await e.open();
  e.document.hidden = true;
  e.document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(e.state.streams[0].track.stops, 1);
  assert.equal(e.get("cameraDialog").open, false);
  e.upload();
  e.window.dispatchEvent(new Event("pagehide"));
  assert.ok(e.state.revoked.length >= 1);
});

test("insecure contexts retain choose-photo and never request live camera access", async () => {
  const e = environment({ secure: false });
  await e.open();
  assert.equal(e.state.requests.length, 0);
  assert.match(e.get("photoError").textContent, /HTTPS or localhost/);
  e.get("choosePhoto").click();
  assert.equal(e.get("cropImage").clicks, 1);
});

test("older browsers keep the native upload input and preview", () => {
  const e = environment({ noDialog: true });
  assert.equal(e.get("cropImage").hidden, false);
  assert.equal(e.get("photoActions").hidden, true);
  e.upload();
  assert.equal(e.get("imagePreviewWrap").hidden, false);
  e.get("removePhoto").click();
  assert.equal(e.get("cropImage").files.length, 0);
  assert.equal(e.get("imagePreviewWrap").hidden, true);
});

test("an image encoding failure keeps capture recoverable", async () => {
  const e = environment({ nullBlob: true });
  await e.open();
  e.get("capturePhoto").click();
  assert.match(e.get("cameraError").textContent, /could not be saved/);
  assert.equal(e.get("capturePhoto").disabled, false);
  e.get("closeCamera").click();
  assert.equal(e.state.streams[0].track.stops, 1);
});

test("PNG encoder fallback retains a matching file extension", async () => {
  const e = environment({ png: true });
  await e.open();
  e.get("capturePhoto").click();
  e.get("usePhoto").click();
  assert.equal(e.get("cropImage").files[0].type, "image/png");
  assert.match(e.get("cropImage").files[0].name, /\.png$/);
});

test("unsupported FileList transfer preserves the selected upload", async () => {
  const e = environment({ transferError: true });
  const file = e.upload();
  await e.open();
  e.get("capturePhoto").click();
  e.get("usePhoto").click();
  assert.equal(e.get("cropImage").files[0], file);
  assert.match(e.get("cameraError").textContent, /could not attach/);
});
