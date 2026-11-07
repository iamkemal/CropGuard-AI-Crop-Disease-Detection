const imageInput = document.getElementById("cropImage");
const preview = document.getElementById("cropImagePreview");
const previewWrap = document.getElementById("imagePreviewWrap");

if (imageInput && preview && previewWrap) {
  let previewUrl = null;

  imageInput.addEventListener("change", () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }

    const [file] = imageInput.files;
    if (!file) {
      preview.removeAttribute("src");
      previewWrap.hidden = true;
      return;
    }

    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    previewWrap.hidden = false;
  });
}
